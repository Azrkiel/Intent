"""One authorized retest preserves six failures and cannot grant an eighth."""

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
from backend.tests.test_planning_fifth_attempt import retained as fifth_setup  # noqa: F401
from backend.tests.test_planning_requalification import collect
from backend.tests.test_planning_requalification import retained as fourth_setup  # noqa: F401
from backend.tests.test_planning_sixth_attempt import grant as sixth_grant
from backend.tests.test_planning_sixth_attempt import retained as sixth_setup  # noqa: F401


@pytest.fixture
def retained(request):
    previous = request.getfixturevalue("sixth_setup")
    config, store, original = previous
    sixth_grant(previous)
    session = store.get(original.id)
    session.planning.sixth_attempt.status = "consumed"
    session.planning.attempts.append(PlanAttempt(
        plan_id=session.planning.attempts[0].plan_id, revision=6,
        requirements_revision=session.revision, passes=["planner:outline"],
        error="Package misses scope exclusions",
    ))
    session.usage.append(session.usage[0].model_copy())
    store.save(session)
    return config, store, session


def grant(retained, **changes):
    config, _, session = retained
    args = dict(
        expected_state_hash=preflight(config, session.id, seventh_attempt=True)["state_hash"],
        approval_text="yes, go ahead please PRIVATE RETEST APPROVAL",
        reason="Qualify merged bounded section validation", implementation_commit="e" * 40,
    )
    return issue(config, session.id, seventh_attempt=True, **(args | changes))


def unchanged_history(current, original):
    assert current.planning.attempts[:6] == original.planning.attempts
    for field in ("extension", "requalification", "fifth_attempt", "sixth_attempt"):
        assert getattr(current.planning, field) == getattr(original.planning, field)
    assert current.usage[:len(original.usage)] == original.usage
    assert current.ledger == original.ledger and current.turns == original.turns
    assert current.brief == original.brief and current.compiler_calls == original.compiler_calls


def test_preflight_is_read_only_and_default_is_exhausted(retained):
    config, store, original = retained
    before = store.get(original.id).model_dump_json(round_trip=True)
    report = preflight(config, original.id, seventh_attempt=True)
    assert report["eligible"] and report["attempt_limit"] == 6
    assert report["seventh_attempt_status"] is None
    assert not report["model_requests_possible"]
    assert store.get(original.id).model_dump_json(round_trip=True) == before
    assert original.id not in json.dumps(report)


@pytest.mark.parametrize("failure", [None, "schema", "budget"])
async def test_one_seventh_attempt_preserves_six_failures_and_blocks_eighth(retained, failure):
    config, store, original = retained
    assert grant(retained)["attempt_limit"] == 7

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
    assert current.planning.seventh_attempt.status == "consumed"
    assert current.planning.approval is None
    unchanged_history(current, original)
    if failure is None:
        assert current.planning.active.revision == 7
    if failure == "budget":
        assert provider.client is None and current.usage == original.usage
    current.planning.status, current.planning.active = "blocked", None
    store.save(current)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)
    with pytest.raises(ValueError):
        grant(retained)


def test_stale_duplicate_and_concurrent_issuance_cannot_replenish(retained):
    config, store, original = retained
    token = preflight(config, original.id, seventh_attempt=True)["state_hash"]
    changed = store.get(original.id)
    changed.usage.append(changed.usage[0].model_copy())
    store.save(changed)
    with pytest.raises(ValueError, match="changed"):
        grant(retained, expected_state_hash=token)
    token = preflight(config, original.id, seventh_attempt=True)["state_hash"]

    def once():
        try:
            return grant(retained, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(result is not None for result in pool.map(lambda _: once(), range(2))) == 1


@pytest.mark.parametrize("mutation", ["mode", "limit", "running", "unapproved", "revision", "success"])
def test_grant_requires_current_approved_six_failure_state(retained, mutation):
    config, store, original = retained
    session = store.get(original.id)
    if mutation == "mode":
        config.mode = "demo"
    elif mutation == "limit":
        config.planning_max_attempts = 1
    elif mutation == "running":
        session.build.status = "running"
    elif mutation == "unapproved":
        session.approved_revision = None
    elif mutation == "revision":
        session.revision += 1
        session.approved_revision = session.revision
    else:
        session.planning.attempts[-1].error = None
    store.save(session)
    assert not preflight(config, original.id, seventh_attempt=True)["eligible"]
    with pytest.raises(ValueError):
        grant(retained)


@pytest.mark.parametrize("action", ["correction", "restart"])
async def test_unused_or_reserved_grant_cannot_be_replayed(retained, action):
    config, store, original = retained
    grant(retained)
    service = PlanningService(store, None, config)
    generator = (
        Engine(store, DemoModels()).turn(store.get(original.id), "Use local storage only")
        if action == "correction" else service.generate(store.get(original.id))
    )
    await anext(generator)
    if action == "restart":
        store.recover()
    await generator.aclose()
    current = store.get(original.id)
    expected_status = "invalidated" if action == "correction" else "consumed"
    assert current.planning.seventh_attempt.status == expected_status
    if action == "restart":
        unchanged_history(current, original)
    assert service.attempt_limit(current) == (6 if action == "correction" else 7)
    with pytest.raises(ValueError):
        grant(retained)


@pytest.mark.parametrize("mutation", ["audit", "attempt", "usage", "session", "sixth_grant", "remove"])
def test_grant_and_all_prior_evidence_are_immutable(retained, mutation):
    _, store, original = retained
    grant(retained)
    current = store.get(original.id)
    if mutation == "audit":
        current.planning.seventh_attempt.approval_text = "Changed approval"
    elif mutation == "attempt":
        current.planning.attempts[-1].error = "Changed failure"
    elif mutation == "usage":
        current.usage.clear()
    elif mutation == "session":
        current.id = "different-session"
    elif mutation == "sixth_grant":
        current.planning.sixth_attempt.reason = "Changed reason"
    else:
        current.planning.seventh_attempt = None
    with pytest.raises(ValueError):
        store.save(current)


@pytest.mark.parametrize("mutation", ["id", "hash", "history", "status", "prior_grant"])
def test_contract_binds_sixth_grant_and_six_attempts(retained, mutation):
    _, store, original = retained
    grant(retained)
    raw = store.get(original.id).model_dump(mode="json", round_trip=True)
    seventh = raw["planning"]["seventh_attempt"]
    if mutation == "id":
        seventh["sixth_attempt_id"] = "another-grant"
    elif mutation == "hash":
        seventh["sixth_attempt_hash"] = "f" * 64
    elif mutation == "history":
        seventh["prior_attempt_hashes"][-1] = "f" * 64
    elif mutation == "status":
        seventh["status"] = "consumed"
    else:
        raw["planning"]["sixth_attempt"] = None
    with pytest.raises(ValueError):
        Session.model_validate(raw)


def test_api_and_operator_redact_grant_and_reject_browser_issuance(retained, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, original = retained
    monkeypatch.setattr(command, "Settings", lambda: config)
    monkeypatch.setattr(command, "require_server_stopped", lambda: None)
    approval, output = tmp_path / "approval.txt", tmp_path / "report.json"
    approval.write_text("yes, go ahead please PRIVATE RETEST APPROVAL", encoding="utf-8")
    args = ["--session-id", original.id, "--output", str(output), "--seventh-attempt"]
    assert command.main(args) == 0
    token = json.loads(output.read_text())["state_hash"]
    args += ["--issue", "--expected-state-hash", token, "--approval-file", str(approval),
             "--reason", "Bounded section repair qualification", "--implementation-commit", "e" * 40]
    assert command.main(args) == 0 and command.main(args) == 1
    public = capsys.readouterr().out + output.read_text()
    assert original.id not in public and "PRIVATE RETEST APPROVAL" not in public
    with TestClient(create_app(config)) as client:
        detail = client.get(f"/api/sessions/{original.id}/plan").json()
        assert detail["attempt_limit"] == 7 and "seventh_attempt" not in detail["planning"]
        response = client.post(f"/api/sessions/{original.id}/plan", json={"seventh_attempt": {}})
        assert response.status_code == 422
    assert "seventh_attempt" not in public_session(store.get(original.id))["planning"]


async def test_concurrent_generation_reserves_only_one_seventh(retained):
    config, store, original = retained
    grant(retained)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Paused(DemoModels):
        async def call(self, session, role, *args):
            calls.append(role)
            if role == "planner:outline":
                assert store.get(session.id).planning.seventh_attempt.status == "consumed"
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


def test_failed_database_write_cannot_leave_a_grant(retained):
    _, store, original = retained
    with store.connect() as db:
        db.execute("""CREATE TRIGGER deny_seventh BEFORE UPDATE ON sessions
            WHEN json_extract(NEW.state, '$.planning.seventh_attempt') IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        grant(retained)
    assert store.get(original.id).planning.seventh_attempt is None


@pytest.mark.parametrize("granted", [False, True])
def test_storage_blocks_ungranted_seventh_and_any_eighth(retained, granted):
    _, store, original = retained
    if granted:
        grant(retained)
    current = store.get(original.id)
    current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 7}))
    if granted:
        current.planning.seventh_attempt.status = "consumed"
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 8}))
    with pytest.raises(ValueError):
        store.save(current)


@pytest.mark.parametrize("mutation", ["remove", "replenish", "identity"])
async def test_consumed_seventh_cannot_be_removed_or_reidentified(retained, mutation):
    config, store, original = retained
    grant(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    if mutation == "remove":
        current.planning.attempts.pop()
        current.planning.seventh_attempt.status = "granted"
    elif mutation == "replenish":
        current.planning.seventh_attempt = None
    else:
        current.planning.attempts[6].plan_id = "another-plan"
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(original.id).planning.attempts) == 7
