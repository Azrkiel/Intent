"""A separately approved sixth attempt cannot renew any prior grant."""

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.demo import DemoModels
from backend.app.domain import Session, public_session
from backend.app.engine import Engine
from backend.app.main import create_app
from backend.app.models import LiveModels, ModelError
from backend.app.planning.contracts import PlanAttempt
from backend.app.planning.service import PlanningService
from backend.planning_extension import issue, preflight
from backend.tests.test_planning_extension import setup as extension_setup  # noqa: F401
from backend.tests.test_planning_fifth_attempt import grant as fifth_grant
from backend.tests.test_planning_fifth_attempt import retained as fifth_setup  # noqa: F401
from backend.tests.test_planning_requalification import collect
from backend.tests.test_planning_requalification import retained as fourth_setup  # noqa: F401


@pytest.fixture
def retained(request):
    previous = request.getfixturevalue("fifth_setup")
    config, store, original = previous
    fifth_grant(previous)
    current = store.get(original.id)
    current.planning.fifth_attempt.status = "consumed"
    current.planning.attempts.append(PlanAttempt(
        plan_id=current.planning.attempts[0].plan_id, revision=5,
        requirements_revision=current.revision, passes=["planner:outline"],
        error="Common rules miss constraints or exclusions",
    ))
    current.usage.append(current.usage[0].model_copy())
    store.save(current)
    return config, store, current


def grant(retained, **changes):
    config, _, current = retained
    args = dict(
        expected_state_hash=preflight(config, current.id, sixth_attempt=True)["state_hash"],
        approval_text="go ahead, do the sixth attempt PRIVATE SIXTH APPROVAL",
        reason="Qualify bounded outline repair", implementation_commit="d" * 40,
    )
    return issue(config, current.id, sixth_attempt=True, **(args | changes))


def unchanged_history(current, original):
    assert current.planning.attempts[:5] == original.planning.attempts
    for field in ("extension", "requalification", "fifth_attempt"):
        assert getattr(current.planning, field) == getattr(original.planning, field)
    assert current.usage[:len(original.usage)] == original.usage


def test_preflight_is_read_only_and_default_is_exhausted(retained):
    config, store, original = retained
    before = store.get(original.id).model_dump_json(round_trip=True)
    result = preflight(config, original.id, sixth_attempt=True)
    assert result["eligible"] and result["attempt_limit"] == 5
    assert result["sixth_attempt_status"] is None
    assert original.id not in json.dumps(result)
    assert store.get(original.id).model_dump_json(round_trip=True) == before
    assert not preflight(config, original.id, fifth_attempt=True)["eligible"]


@pytest.mark.parametrize("failure", [None, "schema", "budget"])
async def test_sixth_attempt_is_bounded_and_preserves_five_failures(retained, failure):
    config, store, original = retained
    assert grant(retained)["attempt_limit"] == 6

    class Failing:
        async def call(self, *args):
            raise ModelError("Invalid JSON after one repair retry")

    provider = DemoModels() if failure is None else Failing()
    if failure == "budget":
        config.session_budget_usd = 0.01
        provider = LiveModels(config)
    events = await collect(PlanningService(store, provider, config), store.get(original.id))
    current = store.get(original.id)
    assert events[-1]["type"] == ("plan_ready" if failure is None else "plan_error")
    assert current.planning.sixth_attempt.status == "consumed"
    assert current.planning.approval is None
    unchanged_history(current, original)
    if failure is None:
        assert current.planning.active.revision == 6
        assert current.planning.active.plan_id == original.planning.attempts[0].plan_id
    else:
        assert current.planning.active is None
    if failure == "budget":
        assert provider.client is None and current.usage == original.usage
    current.planning.status, current.planning.active = "blocked", None
    store.save(current)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)
    with pytest.raises(ValueError):
        grant(retained)


def test_duplicate_concurrent_and_stale_issuance_are_rejected(retained):
    config, store, original = retained
    token = preflight(config, original.id, sixth_attempt=True)["state_hash"]
    changed = store.get(original.id)
    changed.usage.append(changed.usage[0].model_copy())
    store.save(changed)
    with pytest.raises(ValueError, match="changed"):
        grant(retained, expected_state_hash=token)
    token = preflight(config, original.id, sixth_attempt=True)["state_hash"]

    def once():
        try:
            return grant(retained, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(result is not None for result in pool.map(lambda _: once(), range(2))) == 1
    with pytest.raises(ValueError):
        store.save(changed)


@pytest.mark.parametrize("mutation", ["mode", "limit", "running", "unapproved", "revision", "success"])
def test_issuance_requires_current_approved_five_failure_state(retained, mutation):
    config, store, original = retained
    current = store.get(original.id)
    if mutation == "mode":
        config.mode = "demo"
    elif mutation == "limit":
        config.planning_max_attempts = 1
    elif mutation == "running":
        current.build.status = "running"
    elif mutation == "unapproved":
        current.approved_revision = None
    elif mutation == "revision":
        current.revision += 1
        current.approved_revision = current.revision
    else:
        current.planning.attempts[4].error = None
    store.save(current)
    assert not preflight(config, original.id, sixth_attempt=True)["eligible"]
    with pytest.raises(ValueError):
        grant(retained)


def test_failed_database_write_does_not_leave_a_grant(retained):
    _, store, original = retained
    with store.connect() as db:
        db.execute("""CREATE TRIGGER deny_sixth BEFORE UPDATE ON sessions
            WHEN json_extract(NEW.state, '$.planning.sixth_attempt') IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        grant(retained)
    assert store.get(original.id).planning.sixth_attempt is None


@pytest.mark.parametrize("action", ["correction", "restart"])
async def test_unused_or_reserved_grant_cannot_be_replayed(retained, action):
    config, store, original = retained
    grant(retained)
    service = PlanningService(store, None, config)
    if action == "correction":
        generator = Engine(store, DemoModels()).turn(store.get(original.id), "Use local storage only")
    else:
        generator = service.generate(store.get(original.id))
    await anext(generator)
    if action == "restart":
        store.recover()
    await generator.aclose()
    current = store.get(original.id)
    assert current.planning.sixth_attempt.status == ("invalidated" if action == "correction" else "consumed")
    unchanged_history(current, original)
    assert service.attempt_limit(current) == (5 if action == "correction" else 6)
    with pytest.raises(ValueError):
        grant(retained)


@pytest.mark.parametrize("mutation", ["remove", "replenish", "identity"])
async def test_consumed_sixth_cannot_be_removed_or_reidentified(retained, mutation):
    config, store, original = retained
    grant(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    if mutation == "remove":
        current.planning.attempts.pop()
        current.planning.sixth_attempt.status = "granted"
    elif mutation == "replenish":
        current.planning.sixth_attempt = None
    else:
        current.planning.attempts[5].plan_id = "different-plan"
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(original.id).planning.attempts) == 6


async def test_concurrent_generation_reserves_only_one_sixth(retained):
    config, store, original = retained
    grant(retained)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Paused(DemoModels):
        async def call(self, session, role, *args):
            calls.append(role)
            if role == "planner:outline":
                assert store.get(session.id).planning.sixth_attempt.status == "consumed"
                entered.set()
                await release.wait()
            return await super().call(session, role, *args)

    first, stale = store.get(original.id), store.get(original.id)
    service = PlanningService(store, Paused(), config)
    task = asyncio.create_task(collect(service, first))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(ValueError, match="changed"):
            await collect(service, stale)
    finally:
        release.set()
        await task
    assert calls.count("planner:outline") == 1


@pytest.mark.parametrize("mutation", ["audit", "prior_attempt", "usage", "session", "prior_grant"])
def test_audit_and_prior_evidence_are_immutable(retained, mutation):
    _, store, original = retained
    grant(retained)
    current = store.get(original.id)
    if mutation == "audit":
        current.planning.sixth_attempt.approval_text = "Changed approval"
    elif mutation == "prior_attempt":
        current.planning.attempts[4].error = "Changed failure"
    elif mutation == "usage":
        current.usage.clear()
    elif mutation == "session":
        current.id = "different-session"
    else:
        current.planning.fifth_attempt.reason = "Changed reason"
    with pytest.raises(ValueError):
        store.save(current)


@pytest.mark.parametrize("mutation", ["id", "hash", "history", "status", "remove"])
def test_contract_binds_fifth_grant_and_five_attempts(retained, mutation):
    _, store, original = retained
    grant(retained)
    raw = store.get(original.id).model_dump(mode="json", round_trip=True)
    sixth = raw["planning"]["sixth_attempt"]
    if mutation == "id":
        sixth["fifth_attempt_id"] = "other-grant"
    elif mutation == "hash":
        sixth["fifth_attempt_hash"] = "f" * 64
    elif mutation == "history":
        sixth["prior_attempt_hashes"][4] = "f" * 64
    elif mutation == "status":
        sixth["status"] = "consumed"
    else:
        raw["planning"]["fifth_attempt"] = None
    with pytest.raises(ValueError):
        Session.model_validate(raw)


@pytest.mark.parametrize("granted", [False, True])
def test_storage_blocks_ungranted_sixth_and_any_seventh(retained, granted):
    _, store, original = retained
    if granted:
        grant(retained)
    current = store.get(original.id)
    current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 6}))
    if granted:
        current.planning.sixth_attempt.status = "consumed"
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 7}))
    with pytest.raises(ValueError):
        store.save(current)


def test_api_and_operator_keep_grant_private(retained, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, original = retained
    monkeypatch.setattr(command, "Settings", lambda: config)
    stopped = []
    monkeypatch.setattr(command, "require_server_stopped", lambda: stopped.append(True))
    approval, output = tmp_path / "approval.txt", tmp_path / "report.json"
    approval.write_text("go ahead, do the sixth attempt PRIVATE SIXTH APPROVAL", encoding="utf-8")
    args = ["--session-id", original.id, "--output", str(output), "--sixth-attempt"]
    assert command.main(args) == 0
    token = json.loads(output.read_text())["state_hash"]
    args += ["--issue", "--expected-state-hash", token, "--approval-file", str(approval),
             "--reason", "Bounded outline repair qualification", "--implementation-commit", "d" * 40]
    assert command.main(args) == 0 and command.main(args) == 1
    assert stopped == [True, True]
    public = capsys.readouterr().out + output.read_text()
    assert original.id not in public and "PRIVATE SIXTH APPROVAL" not in public
    with TestClient(create_app(config)) as client:
        detail = client.get(f"/api/sessions/{original.id}/plan").json()
        assert detail["attempt_limit"] == 6 and "sixth_attempt" not in detail["planning"]
        assert client.post(f"/api/sessions/{original.id}/plan", json={"sixth_attempt": {}}).status_code == 422
    assert "sixth_attempt" not in public_session(store.get(original.id))["planning"]


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_sixth_uses_only_existing_shared_outline_repair(retained, repair_succeeds):
    import httpx
    from openai import AsyncOpenAI

    from backend.app.planning.demo import demo_response
    from backend.tests.planning_fixtures import repair_response
    from backend.tests.test_models import completion

    config, store, original = retained
    grant(retained)
    session = store.get(original.id)
    requests = []
    roles = iter([
        "planner:screen:main", "planner:phase:foundation", "planner:phase:implementation", "planner:verify",
    ])

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        role = "planner:outline" if len(requests) <= 2 else next(roles)
        payload = json.loads(body["messages"][1]["content"])
        result = demo_response(session, role, payload)
        if len(requests) == 1 or not repair_succeeds:
            result["common_rules"] = []
        return httpx.Response(200, json=completion(json.dumps(repair_response(body, result))))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(config, client=client)
    try:
        events = await collect(PlanningService(store, provider, config), session)
    finally:
        await provider.close()
    current = store.get(original.id)
    assert len(requests) == (6 if repair_succeeds else 2)
    assert len(current.usage) == len(original.usage) + len(requests)
    assert events[-1]["type"] == ("plan_ready" if repair_succeeds else "plan_error")
    assert current.planning.sixth_attempt.status == "consumed"
    assert current.planning.approval is None
    unchanged_history(current, original)
