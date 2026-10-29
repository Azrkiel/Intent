"""Only the reserved eighth attempt can spend two audited overload retries."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.domain import Delta
from backend.app.models import LiveModels, ModelError
from backend.app.planning.service import PlanningService
from backend.tests.test_models import completion
from backend.tests.test_planning_eighth_attempt import (  # noqa: F401
    extension_setup,
    fifth_setup,
    fourth_setup,
    grant,
    seventh_setup,
    sixth_setup,
)
from backend.tests.test_planning_eighth_attempt import retained as eighth_setup  # noqa: F401


@pytest.fixture
async def reserved(request):
    retained_state = request.getfixturevalue("eighth_setup")
    config, store, original = retained_state
    grant(retained_state)
    session = store.get(original.id)
    generator = PlanningService(store, None, config).generate(session)
    await anext(generator)
    session.planning.attempts[-1].passes.append("planner:outline")
    store.save(session)
    yield config, store, session
    await generator.aclose()


def provider(config, handle):
    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    return LiveModels(config, client=client)


def busy(status=529, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, json={"error": {
        "type": "server_error", "message": "worker overloaded",
    }})


async def invoke(model, session, role="planner:outline"):
    return await model.call(session, role, Delta, "Return a delta", {})


async def test_one_overload_recovers_without_using_content_repair(reserved, monkeypatch):
    config, store, session = reserved
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(json.loads(request.content))
        return busy() if len(requests) == 1 else httpx.Response(200, json=completion("{}"))

    model = provider(config, handle)
    try:
        await invoke(model, session)
        assert delays == [3]
        assert len(requests) == 2 and requests[0] == requests[1]
        assert len(session.usage) == len(store.get(session.id).usage) + 1
        retries = session.planning.eighth_attempt.transport_retries
        assert len(retries) == 1 and retries[0].http_status == 529
        assert retries[0].estimated_cost_reserve_usd > 0
        store.save(session)
        assert store.get(session.id).planning.eighth_attempt.transport_retries == retries
        assert model.reserved[session.id] == 0
    finally:
        await model.close()


async def test_shared_quota_stops_after_two_overloads_across_roles(reserved, monkeypatch):
    config, store, session = reserved
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy() if len(requests) in (1, 3, 4) else httpx.Response(200, json=completion("{}"))

    model = provider(config, handle)
    try:
        await invoke(model, session)
        session.planning.attempts[-1].passes.append("planner:screen:main")
        store.save(session)
        with pytest.raises(ModelError):
            await invoke(model, session, "planner:screen:main")
        assert len(requests) == 4 and delays == [3, 10]
        assert len(session.planning.eighth_attempt.transport_retries) == 2
        assert model.reserved[session.id] == 0
    finally:
        await model.close()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
async def test_other_http_errors_do_not_retry(reserved, status):
    config, _, session = reserved
    requests = []

    def handle(request):
        requests.append(request)
        return busy(status)

    model = provider(config, handle)
    try:
        with pytest.raises(ModelError):
            await invoke(model, session)
        assert len(requests) == 1 and session.planning.eighth_attempt.transport_retries == []
        assert model.reserved[session.id] == 0
    finally:
        await model.close()


@pytest.mark.parametrize("kind", ["connect", "timeout"])
async def test_ambiguous_transport_failures_do_not_retry(reserved, kind):
    config, _, session = reserved
    requests = []

    def handle(request):
        requests.append(request)
        error = httpx.ConnectError if kind == "connect" else httpx.ReadTimeout
        raise error("offline transport failure", request=request)

    model = provider(config, handle)
    try:
        with pytest.raises(ModelError):
            await invoke(model, session)
        assert len(requests) == 1 and session.planning.eighth_attempt.transport_retries == []
    finally:
        await model.close()


@pytest.mark.parametrize("retry_after,expected", [("7", 7), ("bad", 3), ("nan", 3), ("60", None)])
async def test_retry_after_is_bounded_and_respected(reserved, monkeypatch, retry_after, expected):
    config, _, session = reserved
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy(retry_after=retry_after) if len(requests) == 1 else httpx.Response(
            200, json=completion("{}"))

    model = provider(config, handle)
    try:
        if expected is None:
            with pytest.raises(ModelError):
                await invoke(model, session)
            assert delays == [] and len(requests) == 1
        else:
            await invoke(model, session)
            assert delays == [expected] and len(requests) == 2
    finally:
        await model.close()


async def test_transport_recovery_and_one_content_repair_have_separate_bounds(reserved, monkeypatch):
    config, _, session = reserved
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return busy()
        content = "invalid JSON" if len(requests) == 2 else "{}"
        return httpx.Response(200, json=completion(content))

    model = provider(config, handle)
    old_usage = len(session.usage)
    try:
        await invoke(model, session)
        assert len(requests) == 3 and delays == [3]
        assert len(session.usage) == old_usage + 2
        assert len(requests[-1]["messages"]) == 4
        assert len(session.planning.eighth_attempt.transport_retries) == 1
    finally:
        await model.close()


async def test_cancelled_backoff_sends_no_extra_request_and_releases_reserve(reserved, monkeypatch):
    config, store, session = reserved
    requests = []

    async def sleep(delay):
        raise asyncio.CancelledError()

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy()

    model = provider(config, handle)
    try:
        with pytest.raises(asyncio.CancelledError):
            await invoke(model, session)
        assert len(requests) == 1 and model.reserved[session.id] == 0
        store.save(session)
        assert len(store.get(session.id).planning.eighth_attempt.transport_retries) == 1
    finally:
        await model.close()


@pytest.mark.parametrize("mutation", ["delete", "rewrite", "third", "unreserved_role"])
async def test_transport_audit_cannot_be_rewritten_or_replenished(reserved, monkeypatch, mutation):
    config, store, session = reserved
    requests = []

    async def sleep(delay):
        pass

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy() if len(requests) == 1 else httpx.Response(200, json=completion("{}"))

    model = provider(config, handle)
    try:
        await invoke(model, session)
        store.save(session)
        current = store.get(session.id)
        retries = current.planning.eighth_attempt.transport_retries
        if mutation == "delete":
            retries.clear()
        elif mutation == "rewrite":
            retries[0].http_status = 503
        elif mutation == "third":
            retries.extend([retries[0].model_copy(), retries[0].model_copy()])
        else:
            retries.append(retries[0].model_copy(update={"role": "planner:phase:unreserved"}))
        with pytest.raises(ValueError):
            store.save(current)
    finally:
        await model.close()


@pytest.mark.parametrize("status", [502, 503, 504])
async def test_explicit_transient_statuses_can_recover(reserved, monkeypatch, status):
    config, _, session = reserved
    requests = []

    async def sleep(delay):
        pass

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy(status) if len(requests) == 1 else httpx.Response(200, json=completion("{}"))

    model = provider(config, handle)
    try:
        await invoke(model, session)
        assert len(requests) == 2
        assert session.planning.eighth_attempt.transport_retries[0].http_status == status
    finally:
        await model.close()


@pytest.mark.parametrize("scope", ["ordinary", "unreserved", "critic", "closed"])
async def test_retry_is_not_enabled_outside_reserved_eighth_planning(reserved, scope):
    from backend.app.domain import Session

    config, _, session = reserved
    role = "planner:outline"
    if scope == "ordinary":
        session = Session(mode="live")
    elif scope == "unreserved":
        role = "planner:screen:not-reserved"
    elif scope == "critic":
        role = "critic:data"
    else:
        session.planning.status = "blocked"
    requests = []

    def handle(request):
        requests.append(request)
        return busy()

    model = provider(config, handle)
    try:
        with pytest.raises(ModelError):
            await invoke(model, session, role)
        assert len(requests) == 1
    finally:
        await model.close()


async def test_retry_budget_is_checked_before_another_http_request(reserved):
    config, _, session = reserved
    requests = []
    model = None

    def handle(request):
        requests.append(request)
        config.session_budget_usd = (
            sum(item.estimated_usd for item in session.usage) + model.reserved[session.id] * 1.5
        )
        return busy()

    model = provider(config, handle)
    try:
        with pytest.raises(ModelError, match="budget"):
            await invoke(model, session)
        assert len(requests) == 1 and session.planning.eighth_attempt.transport_retries == []
        assert model.reserved[session.id] == 0
    finally:
        await model.close()


async def test_retry_risk_is_preserved_in_later_budget_checks(reserved, monkeypatch):
    config, store, session = reserved
    requests = []

    async def sleep(delay):
        pass

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy() if len(requests) == 1 else httpx.Response(200, json=completion("{}"))

    model = provider(config, handle)
    try:
        await invoke(model, session)
        store.save(session)
        restored = store.get(session.id)
        risk = model.retry_risk(restored)
        assert risk > 0
        config.session_budget_usd = sum(u.estimated_usd for u in restored.usage) + risk / 2
        with pytest.raises(ModelError, match="budget"):
            await invoke(model, restored)
        assert len(requests) == 2
    finally:
        await model.close()


async def test_sdk_retry_layer_cannot_multiply_application_retries(reserved, monkeypatch):
    config, _, session = reserved
    requests = []

    async def sleep(delay):
        pass

    monkeypatch.setattr("backend.app.models.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return busy()

    client = AsyncOpenAI(api_key="offline-test", base_url="https://test.invalid/v1", max_retries=2,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    model = LiveModels(config, client=client)
    try:
        with pytest.raises(ModelError):
            await invoke(model, session)
        assert len(requests) == 3
        assert len(session.planning.eighth_attempt.transport_retries) == 2
    finally:
        await model.close()
