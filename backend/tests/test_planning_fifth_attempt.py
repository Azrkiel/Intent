"""One separately authorized fifth attempt, preserving all prior evidence."""

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
from backend.tests.test_planning_requalification import collect, qualify
from backend.tests.test_planning_requalification import retained as fourth_setup  # noqa: F401


@pytest.fixture
def retained(request):
    previous = request.getfixturevalue("fourth_setup")
    config, store, original = previous
    qualify(previous)
    session = store.get(original.id)
    session.planning.requalification.status = "consumed"
    session.planning.attempts.append(PlanAttempt(
        plan_id=session.planning.attempts[0].plan_id, revision=4,
        requirements_revision=session.revision, passes=["planner:outline"],
        error="Retained fourth-attempt Unicode rejection",
    ))
    session.usage.append(session.usage[0].model_copy())
    store.save(session)
    return config, store, session


def grant(retained, **changes):
    config, _, original = retained
    args = dict(
        expected_state_hash=preflight(config, original.id, fifth_attempt=True)["state_hash"],
        approval_text="try a fifth please, let's make this work PRIVATE FIFTH APPROVAL",
        reason="Qualify merged bounded Unicode planning", implementation_commit="c" * 40,
    )
    return issue(config, original.id, fifth_attempt=True, **(args | changes))


def test_preflight_preserves_default_exhaustion_and_raw_state(retained):
    config, store, original = retained
    before = store.get(original.id).model_dump_json(round_trip=True)
    report = preflight(config, original.id, fifth_attempt=True)
    assert report["eligible"] and report["attempt_limit"] == 4
    assert report["fifth_attempt_status"] is None
    assert original.id not in json.dumps(report)
    assert store.get(original.id).model_dump_json(round_trip=True) == before
    assert not preflight(config, original.id, requalification=True)["eligible"]


async def test_fifth_success_preserves_history_stops_at_review_and_blocks_sixth(retained):
    config, store, original = retained
    assert grant(retained)["attempt_limit"] == 5
    events = await collect(PlanningService(store, DemoModels(), config), store.get(original.id))
    current = store.get(original.id)
    assert events[-1]["type"] == "plan_ready"
    assert current.planning.active.revision == 5
    assert current.planning.active.plan_id == original.planning.attempts[0].plan_id
    assert current.planning.approval is None
    assert current.planning.fifth_attempt.status == "consumed"
    assert current.planning.attempts[:4] == original.planning.attempts
    assert current.planning.extension == original.planning.extension
    assert current.planning.requalification == original.planning.requalification
    assert current.usage[:len(original.usage)] == original.usage
    assert current.brief == original.brief and current.approved_revision == original.approved_revision
    current.planning.status, current.planning.active = "blocked", None
    store.save(current)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)
    with pytest.raises(ValueError):
        grant(retained)


async def test_failure_consumes_fifth_without_retry(retained):
    config, store, original = retained
    grant(retained)

    class Failing:
        async def call(self, *args):
            raise ModelError("Invalid JSON after one repair retry")

    events = await collect(PlanningService(store, Failing(), config), store.get(original.id))
    current = store.get(original.id)
    assert events[-1]["type"] == "plan_error"
    assert current.planning.fifth_attempt.status == "consumed"
    assert current.planning.active is current.planning.approval is None
    assert current.planning.attempts[:4] == original.planning.attempts
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)


def test_duplicate_and_concurrent_issuance_is_atomic(retained):
    config, store, original = retained
    token = preflight(config, original.id, fifth_attempt=True)["state_hash"]

    def once():
        try:
            return grant(retained, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(value is not None for value in pool.map(lambda _: once(), range(2))) == 1
    with pytest.raises(ValueError):
        grant(retained)
    with pytest.raises(ValueError):
        store.save(original)


def test_stale_preflight_cannot_issue(retained):
    config, store, original = retained
    token = preflight(config, original.id, fifth_attempt=True)["state_hash"]
    current = store.get(original.id)
    current.usage.append(current.usage[0].model_copy())
    store.save(current)
    with pytest.raises(ValueError, match="changed"):
        grant(retained, expected_state_hash=token)
    assert store.get(original.id).planning.fifth_attempt is None


def test_failed_write_does_not_leave_grant(retained):
    _, store, original = retained
    with store.connect() as db:
        db.execute("""CREATE TRIGGER deny_fifth BEFORE UPDATE ON sessions
            WHEN json_extract(NEW.state, '$.planning.fifth_attempt') IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        grant(retained)
    assert store.get(original.id).planning.fifth_attempt is None


@pytest.mark.parametrize("mutation", ["mode", "limit", "running", "unapproved", "revision", "success"])
def test_issuance_requires_current_approved_four_failure_state(retained, mutation):
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
        current.planning.attempts[3].error = None
    store.save(current)
    assert not preflight(config, original.id, fifth_attempt=True)["eligible"]
    with pytest.raises(ValueError):
        grant(retained)


async def test_fifth_keeps_existing_budget_guard_before_provider(retained):
    config, store, original = retained
    grant(retained)
    config.session_budget_usd = 0.01
    provider = LiveModels(config)
    events = await collect(PlanningService(store, provider, config), store.get(original.id))
    assert events[-1]["type"] == "plan_error"
    assert provider.client is None
    current = store.get(original.id)
    assert current.planning.fifth_attempt.status == "consumed"
    assert current.usage == original.usage
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)


async def test_correction_invalidates_unused_fifth_grant(retained):
    config, store, original = retained
    grant(retained)
    generator = Engine(store, DemoModels()).turn(store.get(original.id), "Use local storage only")
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    assert current.planning.fifth_attempt.status == "invalidated"
    assert current.planning.requalification == original.planning.requalification
    assert current.planning.attempts == original.planning.attempts
    assert PlanningService(None, None, config).attempt_limit(current) == 4
    with pytest.raises(ValueError):
        grant(retained)


async def test_restart_consumes_fifth_without_replay(retained):
    config, store, original = retained
    grant(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    store.recover()
    current = store.get(original.id)
    assert current.planning.status == "blocked"
    assert current.planning.fifth_attempt.status == "consumed"
    assert current.planning.attempts[:4] == original.planning.attempts
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)
    await generator.aclose()


@pytest.mark.parametrize("mutation", ["remove", "replenish", "identity"])
async def test_consumed_fifth_cannot_be_removed_replenished_or_reidentified(retained, mutation):
    config, store, original = retained
    grant(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    if mutation == "remove":
        current.planning.attempts.pop()
        current.planning.fifth_attempt.status = "granted"
    elif mutation == "replenish":
        current.planning.fifth_attempt = None
    else:
        current.planning.attempts[4].plan_id = "different-plan"
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(original.id).planning.attempts) == 5


async def test_concurrent_dispatch_only_reserves_one_fifth_attempt(retained):
    config, store, original = retained
    grant(retained)
    first, stale = store.get(original.id), store.get(original.id)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Paused(DemoModels):
        async def call(self, session, role, *args):
            calls.append(role)
            if role == "planner:outline":
                saved = store.get(session.id)
                assert saved.planning.fifth_attempt.status == "consumed"
                assert len(saved.planning.attempts) == 5
                entered.set()
                await release.wait()
            return await super().call(session, role, *args)

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


@pytest.mark.parametrize("mutation", ["grant", "history", "usage", "session", "previous_grant"])
def test_saved_grant_and_prior_evidence_cannot_be_rewritten(retained, mutation):
    _, store, original = retained
    grant(retained)
    current = store.get(original.id)
    if mutation == "grant":
        current.planning.fifth_attempt.approval_text = "Different approval"
    elif mutation == "history":
        current.planning.attempts[3].error = "Different failure"
    elif mutation == "usage":
        current.usage.clear()
    elif mutation == "session":
        current.id = "different-session"
    else:
        current.planning.requalification.reason = "Rewritten reason"
    with pytest.raises(ValueError):
        store.save(current)


@pytest.mark.parametrize("mutation", ["previous_id", "previous_hash", "prior_hash", "consumed", "remove"])
def test_contract_requires_bound_fourth_grant_and_four_attempt_hashes(retained, mutation):
    _, store, original = retained
    grant(retained)
    raw = store.get(original.id).model_dump(mode="json", round_trip=True)
    fifth = raw["planning"]["fifth_attempt"]
    if mutation == "previous_id":
        fifth["requalification_id"] = "different-grant"
    elif mutation == "previous_hash":
        fifth["requalification_hash"] = "f" * 64
    elif mutation == "prior_hash":
        fifth["prior_attempt_hashes"][3] = "f" * 64
    elif mutation == "consumed":
        fifth["status"] = "consumed"
    else:
        raw["planning"]["requalification"] = None
    with pytest.raises(ValueError):
        Session.model_validate(raw)


@pytest.mark.parametrize("granted", [False, True])
def test_storage_refuses_ungranted_fifth_and_any_sixth(retained, granted):
    _, store, original = retained
    if granted:
        grant(retained)
    current = store.get(original.id)
    current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 5}))
    if granted:
        current.planning.fifth_attempt.status = "consumed"
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 6}))
    with pytest.raises(ValueError):
        store.save(current)


def test_api_redacts_grant_audit_and_shares_effective_limit(retained):
    config, store, original = retained
    grant(retained)
    with TestClient(create_app(config)) as client:
        detail = client.get(f"/api/sessions/{original.id}/plan").json()
        assert detail["attempt_limit"] == 5
        assert "fifth_attempt" not in detail["planning"]
        assert "PRIVATE FIFTH APPROVAL" not in json.dumps(detail)
        assert client.post(f"/api/sessions/{original.id}/plan", json={"fifth_attempt": {}}).status_code == 422
    assert "fifth_attempt" not in public_session(store.get(original.id))["planning"]


def test_cli_requires_stopped_server_and_hides_approval(retained, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, original = retained
    monkeypatch.setattr(command, "Settings", lambda: config)
    checks = []
    monkeypatch.setattr(command, "require_server_stopped", lambda: checks.append(True))
    approval, output = tmp_path / "approval.txt", tmp_path / "report.json"
    approval.write_text("try a fifth please PRIVATE FIFTH APPROVAL", encoding="utf-8")
    common = ["--session-id", original.id, "--output", str(output), "--fifth-attempt"]
    assert command.main(common) == 0
    token = json.loads(output.read_text())["state_hash"]
    issuance = common + ["--issue", "--expected-state-hash", token, "--approval-file", str(approval),
                         "--reason", "Bounded Unicode qualification", "--implementation-commit", "c" * 40]
    assert command.main(issuance) == 0
    assert command.main(issuance) == 1
    assert checks == [True, True]
    assert store.get(original.id).planning.fifth_attempt.status == "granted"
    public = capsys.readouterr().out + output.read_text()
    assert original.id not in public and "PRIVATE FIFTH APPROVAL" not in public
