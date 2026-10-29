import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.demo import DemoModels
from backend.app.domain import Session, Usage, public_session
from backend.app.engine import Engine
from backend.app.main import create_app
from backend.app.models import ModelError
from backend.app.planning.contracts import PlanAttempt
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.planning_extension import issue, preflight
from backend.tests.planning_fixtures import ready_session


@pytest.fixture
def setup(tmp_path):
    config = Settings(mode="live", database_path=str(tmp_path / "sessions.db"))
    store = Store(config.database_path)
    session = ready_session()
    session.mode = "live"
    session.planning.status = "blocked"
    session.planning.attempts = [
        PlanAttempt(
            plan_id="retained-plan", revision=n, requirements_revision=session.revision,
            passes=["planner:outline"], error="Retained failed outline",
        ) for n in (1, 2)
    ]
    session.usage = [
        Usage(role="planner:outline", model="synthetic", input_tokens=1,
              output_tokens=1, estimated_usd=0.01, latency_ms=1)
        for _ in range(2)
    ]
    store.save(session)
    return config, store, session


def grant(setup, **changes):
    config, _, session = setup
    args = dict(
        expected_state_hash=preflight(config, session.id)["state_hash"],
        approval_text="I approve one extra attempt. PRIVATE APPROVAL",
        reason="Qualify the corrected ASCII schema", implementation_commit="a" * 40,
    )
    return issue(config, session.id, **(args | changes))


async def collect(service, session):
    return [event async for event in service.generate(session)]


def test_preflight_is_read_only_and_redacted(setup):
    config, store, session = setup
    before = store.get(session.id).model_dump_json(round_trip=True)
    result = preflight(config, session.id)
    assert result["eligible"] and result["attempt_limit"] == 2
    assert result["attempts_consumed"] == 2 and len(result["state_hash"]) == 64
    assert session.id not in json.dumps(result)
    assert before == store.get(session.id).model_dump_json(round_trip=True)


async def test_grant_allows_only_third_attempt_and_keeps_plan_review_separate(setup):
    config, store, original = setup
    result = grant(setup)
    assert result["attempt_limit"] == 3 and result["extension_status"] == "granted"
    session = store.get(original.id)
    assert session.planning.attempts == original.planning.attempts
    assert session.usage == original.usage
    assert session.planning.extension.approval_text.endswith("PRIVATE APPROVAL")
    service = PlanningService(store, DemoModels(), config)
    events = await collect(service, session)
    assert events[-1]["type"] == "plan_ready"
    assert session.planning.active.revision == 3
    assert session.planning.attempts[-1].plan_id == "retained-plan"
    assert session.planning.approval is None
    assert session.planning.extension.status == "consumed"
    assert session.planning.attempts[:2] == original.planning.attempts
    assert session.usage[:2] == original.usage
    assert len(await collect(service, session)) == 1  # Cached, no fourth attempt.
    session.planning.status, session.planning.active = "blocked", None
    store.save(session)
    with pytest.raises(ValueError, match="allowance"):
        await collect(service, session)
    with pytest.raises(ValueError, match="extension"):
        grant(setup)


@pytest.mark.parametrize("change", ["correction", "usage", "attempt", "approval"])
def test_issuance_rejects_stale_preflight_without_mutation(setup, change):
    config, store, session = setup
    token = preflight(config, session.id)["state_hash"]
    if change == "correction":
        session.revision += 1
        session.approved_revision = None
    elif change == "usage":
        session.usage.append(session.usage[0].model_copy())
    elif change == "attempt":
        session.planning.attempts[0].error = "Changed diagnosis"
    else:
        session.approved_revision = None
    store.save(session)
    with pytest.raises(ValueError):
        grant(setup, expected_state_hash=token)
    assert store.get(session.id).planning.extension is None


def test_duplicate_and_concurrent_grants_never_multiply_allowance(setup):
    config, store, session = setup
    token = preflight(config, session.id)["state_hash"]

    def once():
        try:
            return grant(setup, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: once(), range(2)))
    assert sum(result is not None for result in results) == 1
    extension = store.get(session.id).planning.extension
    assert preflight(config, session.id)["attempt_limit"] == 3
    with pytest.raises(ValueError, match="extension"):
        grant(setup)
    assert store.get(session.id).planning.extension == extension


async def test_stale_loaded_session_cannot_erase_grant_or_duplicate_dispatch(setup):
    config, store, original = setup
    grant(setup)
    with pytest.raises(ValueError, match="extension"):
        store.save(original)
    first, second = store.get(original.id), store.get(original.id)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Paused(DemoModels):
        async def call(self, session, role, *args):
            calls.append(role)
            if role == "planner:outline":
                entered.set()
                await release.wait()
            return await super().call(session, role, *args)

    service = PlanningService(store, Paused(), config)
    task = asyncio.create_task(collect(service, first))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(ValueError, match="changed"):
            await collect(service, second)
    finally:
        release.set()
        await task
    assert calls.count("planner:outline") == 1
    assert len(store.get(original.id).planning.attempts) == 3


async def test_correction_invalidates_unused_grant_without_renewal(setup):
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    engine = Engine(store, DemoModels())
    generator = engine.turn(session, "Use browser storage only")
    await anext(generator)
    await generator.aclose()
    restored = store.get(session.id)
    assert restored.planning.extension.status == "invalidated"
    assert restored.planning.attempts == original.planning.attempts
    assert PlanningService(store, None, config).attempt_limit(restored) == 2
    with pytest.raises(ValueError):
        grant(setup)


async def test_restart_or_interruption_consumes_grant_and_preserves_history(setup):
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    service = PlanningService(store, DemoModels(), config)
    generator = service.generate(session)
    await anext(generator)
    store.recover()
    restored = store.get(session.id)
    assert restored.planning.status == "blocked"
    assert restored.planning.extension.status == "consumed"
    assert len(restored.planning.attempts) == 3
    with pytest.raises(ValueError, match="allowance"):
        await collect(service, restored)
    await generator.aclose()


@pytest.mark.parametrize("failure", ["schema", "semantic", "pass_limit"])
async def test_third_attempt_failure_remains_closed_and_charged(setup, failure):
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    if failure == "pass_limit":
        config.planning_max_passes = 1

    class Failing(DemoModels):
        async def call(self, current, role, *args):
            if failure == "schema":
                current.usage.append(current.usage[0].model_copy())
                raise ModelError("Invalid JSON after one repair retry")
            result = await super().call(current, role, *args)
            if failure == "semantic" and role == "planner:verify":
                result.reviewed_statement_ids = []
            return result

    events = await collect(PlanningService(store, Failing(), config), session)
    assert events[-1]["type"] == "plan_error"
    restored = store.get(session.id)
    assert restored.planning.status == "blocked"
    assert restored.planning.active is None and restored.planning.approval is None
    assert restored.planning.extension.status == "consumed"
    assert restored.usage[:2] == original.usage
    assert len(restored.usage) == (3 if failure == "schema" else 2)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(store, None, config), restored)


def test_storage_rejects_ungranted_third_attempt_and_tampered_grant(setup):
    _, store, session = setup
    session.planning.attempts.append(session.planning.attempts[-1].model_copy(update={"revision": 3}))
    with pytest.raises((ValueError, ValidationError), match="extension"):
        store.save(session)
    session.planning.attempts.pop()
    grant(setup)
    current = store.get(session.id)
    current.planning.extension.approval_text = "Replaced approval"
    with pytest.raises(ValueError, match="extension"):
        store.save(current)
    current = store.get(session.id)
    current.usage.clear()
    with pytest.raises(ValueError, match="usage"):
        store.save(current)


def test_grant_is_bound_to_session_and_prior_attempts(setup):
    _, store, session = setup
    grant(setup)
    current = store.get(session.id)
    current.id = "different-session"
    with pytest.raises(ValueError, match="extension"):
        store.save(current)
    current = store.get(session.id)
    current.planning.attempts[0].error = "Rewrite history"
    with pytest.raises(ValueError, match="extension"):
        store.save(current)
    raw = store.get(session.id).model_dump(mode="json", round_trip=True)
    raw["planning"]["extension"]["status"] = "consumed"
    with pytest.raises(ValidationError):
        Session.model_validate(raw)


@pytest.mark.parametrize("success", [True, False])
def test_api_uses_grant_limit_and_keeps_audit_private(setup, success):
    config, store, session = setup
    grant(setup)
    with TestClient(create_app(config)) as client:
        async def failing(*args):
            raise ModelError("Synthetic outline failure")

        client.app.state.engine.models.call = DemoModels().call if success else failing
        detail = client.get(f"/api/sessions/{session.id}/plan").json()
        assert detail["attempt_limit"] == 3
        assert "PRIVATE APPROVAL" not in json.dumps(detail)
        assert "extension" not in detail["planning"]
        response = client.post(f"/api/sessions/{session.id}/plan", json={"extension": {}})
        assert response.status_code == 422
        response = client.post(f"/api/sessions/{session.id}/plan", json={})
        assert response.status_code == 200 and "PRIVATE APPROVAL" not in response.text
        assert '"type": "plan_ready"' in response.text if success else '"type": "plan_error"' in response.text
        assert client.get(f"/api/sessions/{session.id}/plan").json()["attempt_limit"] == 3
        assert client.get(f"/api/sessions/{session.id}/plan/bundle").status_code == 409
        if not success:
            assert client.post(f"/api/sessions/{session.id}/plan", json={}).status_code == 409
        assert "PRIVATE APPROVAL" not in json.dumps(public_session(store.get(session.id)))


def test_settings_default_cap_is_unchanged():
    assert Settings().planning_max_attempts == 2
    with pytest.raises(ValidationError):
        Settings(planning_max_attempts=3)


async def test_unsaved_ledger_change_never_reaches_model(setup):
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    session.ledger[0].text = "Unsaved changed requirement"
    with pytest.raises(ValueError, match="changed"):
        await collect(PlanningService(store, None, config), session)
    assert len(store.get(original.id).planning.attempts) == 2


@pytest.mark.parametrize("valid_repair", [True, False])
async def test_granted_attempt_preserves_single_real_adapter_repair(setup, valid_repair):
    import httpx
    from openai import AsyncOpenAI

    from backend.app.models import LiveModels
    from backend.app.planning.demo import demo_response
    from backend.tests.test_models import completion

    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    requests = []
    roles = ["planner:outline", "planner:screen:main", "planner:phase:foundation",
             "planner:phase:implementation", "planner:verify"]

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1 or not valid_repair:
            return httpx.Response(200, json=completion("Invalid JSON"))
        payload = json.loads(body["messages"][1]["content"])
        response = demo_response(session, roles[len(requests) - 2], payload)
        return httpx.Response(200, json=completion(json.dumps(response)))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    try:
        events = await collect(PlanningService(store, LiveModels(config, client=client), config), session)
    finally:
        await client.close()
    assert len(requests) == (6 if valid_repair else 2)
    assert len(store.get(session.id).usage) == 2 + len(requests)
    assert events[-1]["type"] == ("plan_ready" if valid_repair else "plan_error")
    assert store.get(session.id).planning.extension.status == "consumed"


@pytest.mark.parametrize("mutation", ["fourth", "remove_third", "remove_grant"])
async def test_consumed_attempt_and_grant_cannot_be_removed_or_expanded(setup, mutation):
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    generator = PlanningService(store, None, config).generate(session)
    await anext(generator)
    await generator.aclose()
    current = store.get(session.id)
    if mutation == "fourth":
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 4}))
    elif mutation == "remove_third":
        current.planning.attempts.pop()
        current.planning.extension.status = "granted"
    else:
        current.planning.attempts = current.planning.attempts[:2]
        current.planning.extension = None
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(session.id).planning.attempts) == 3


def test_operator_cli_preflight_issue_and_failure_reports_are_redacted(setup, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, session = setup
    monkeypatch.setattr(command, "Settings", lambda: config)
    monkeypatch.setattr(command, "require_server_stopped", lambda: None)
    marker, approval, output = (tmp_path / name for name in ("session.txt", "approval.txt", "report.json"))
    marker.write_text(session.id, encoding="utf-8")
    approval.write_text("PRIVATE APPROVAL: one extra attempt.", encoding="utf-8")
    common = ["--session-id-file", str(marker), "--output", str(output)]
    assert command.main(common) == 0
    token = json.loads(output.read_text())["state_hash"]
    assert store.get(session.id).planning.extension is None
    issuance = common + ["--issue", "--expected-state-hash", token,
                         "--approval-file", str(approval), "--reason", "Schema correction",
                         "--implementation-commit", "a" * 40]
    assert command.main(issuance) == 0
    assert command.main(issuance) == 1
    public = capsys.readouterr().out + output.read_text()
    assert session.id not in public and "PRIVATE APPROVAL" not in public
    assert json.loads(output.read_text())["failure"] == "extension_preconditions_failed"


def test_operator_cli_blocks_issuance_while_server_is_active(setup, tmp_path, monkeypatch):
    from backend import planning_extension as command

    config, store, session = setup
    monkeypatch.setattr(command, "Settings", lambda: config)

    def active():
        raise ValueError("Server active")

    monkeypatch.setattr(command, "require_server_stopped", active)
    approval = tmp_path / "approval.txt"
    approval.write_text("Approved", encoding="utf-8")
    output = tmp_path / "report.json"
    assert command.main([
        "--session-id", session.id, "--output", str(output), "--issue",
        "--expected-state-hash", preflight(config, session.id)["state_hash"],
        "--approval-file", str(approval), "--reason", "Schema fix",
        "--implementation-commit", "a" * 40,
    ]) == 1
    assert store.get(session.id).planning.extension is None


async def test_granted_attempt_cannot_bypass_existing_dollar_budget(setup):
    from backend.app.models import LiveModels

    config, store, original = setup
    grant(setup)
    config.session_budget_usd = 0.01
    session = store.get(original.id)
    provider = LiveModels(config)
    events = await collect(PlanningService(store, provider, config), session)
    assert events[-1]["type"] == "plan_error" and "budget" in events[-1]["message"].lower()
    assert provider.client is None
    assert store.get(session.id).usage == original.usage
    assert store.get(session.id).planning.extension.status == "consumed"


@pytest.mark.parametrize("change", ["mode", "limit", "running", "active", "old_revision", "success"])
def test_issuance_rejects_ineligible_state(setup, change):
    config, store, session = setup
    if change == "mode":
        config.mode = "demo"
    elif change == "limit":
        config.planning_max_attempts = 1
    elif change == "running":
        session.build.status = "running"
    elif change == "active":
        from backend.app.planning.contracts import PlanApproval

        session.planning.active = PlanApproval(
            plan_id="retained-plan", revision=2, content_hash="b" * 64, requirements_revision=1,
        )
    elif change == "old_revision":
        session.planning.attempts[0].requirements_revision = 0
    else:
        session.planning.attempts[0].error = None
    store.save(session)
    assert not preflight(config, session.id)["eligible"]
    with pytest.raises(ValueError):
        grant(setup)
    assert store.get(session.id).planning.extension is None
