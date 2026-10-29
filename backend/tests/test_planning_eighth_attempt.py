"""The eighth grant preserves all seven attempts and cannot enable a ninth."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.demo import DemoModels
from backend.app.domain import Session, public_session
from backend.app.engine import Engine
from backend.app.main import create_app
from backend.app.models import ModelError
from backend.app.planning.contracts import PlanAttempt
from backend.app.planning.service import PlanningService
from backend.planning_extension import issue, preflight
from backend.tests.test_planning_extension import setup as extension_setup  # noqa: F401
from backend.tests.test_planning_fifth_attempt import retained as fifth_setup  # noqa: F401
from backend.tests.test_planning_requalification import collect
from backend.tests.test_planning_requalification import retained as fourth_setup  # noqa: F401
from backend.tests.test_planning_seventh_attempt import grant as seventh_grant
from backend.tests.test_planning_seventh_attempt import retained as seventh_setup  # noqa: F401
from backend.tests.test_planning_sixth_attempt import retained as sixth_setup  # noqa: F401


@pytest.fixture
def retained(request):
    previous = request.getfixturevalue("seventh_setup")
    config, store, original = previous
    seventh_grant(previous)
    session = store.get(original.id)
    session.planning.seventh_attempt.status = "consumed"
    session.planning.attempts.append(PlanAttempt(
        plan_id=session.planning.attempts[0].plan_id, revision=7,
        requirements_revision=session.revision, passes=["planner:outline", "planner:screen:main"],
        error="Token Factory planner:screen:main request failed (HTTP 529).",
    ))
    session.usage.append(session.usage[0].model_copy())
    store.save(session)
    return config, store, session


def grant(retained, **changes):
    config, _, session = retained
    args = dict(
        expected_state_hash=preflight(config, session.id, eighth_attempt=True)["state_hash"],
        approval_text="you can run an eigth attempt PRIVATE EIGHTH APPROVAL",
        reason="Apply the seven-attempt review with bounded transport recovery",
        implementation_commit="f" * 40,
    )
    return issue(config, session.id, eighth_attempt=True, **(args | changes))


def assert_history(current, original):
    assert current.planning.attempts[:7] == original.planning.attempts
    for field in ("extension", "requalification", "fifth_attempt", "sixth_attempt", "seventh_attempt"):
        assert getattr(current.planning, field) == getattr(original.planning, field)
    assert current.usage[:len(original.usage)] == original.usage
    assert current.ledger == original.ledger and current.turns == original.turns
    assert current.brief == original.brief and current.compiler_calls == original.compiler_calls


def test_preflight_is_read_only_and_default_allowance_is_exhausted(retained):
    config, store, original = retained
    before = store.get(original.id).model_dump_json(round_trip=True)
    report = preflight(config, original.id, eighth_attempt=True)
    assert report["eligible"] and report["attempt_limit"] == 7
    assert report["eighth_attempt_status"] is None and not report["model_requests_possible"]
    assert original.id not in json.dumps(report)
    assert store.get(original.id).model_dump_json(round_trip=True) == before


@pytest.mark.parametrize("failure", [False, True])
async def test_eighth_reservation_preserves_history_and_blocks_ninth(retained, failure):
    config, store, original = retained
    assert grant(retained)["attempt_limit"] == 8

    class Failing:
        async def call(self, *args):
            raise ModelError("synthetic bounded failure")

    provider = Failing() if failure else DemoModels()
    events = await collect(PlanningService(store, provider, config), store.get(original.id))
    current = store.get(original.id)
    assert events[-1]["type"] == ("plan_error" if failure else "plan_ready")
    assert current.planning.eighth_attempt.status == "consumed"
    assert current.planning.eighth_attempt.transport_retries == []
    assert current.planning.approval is None
    assert_history(current, original)
    current.planning.status, current.planning.active = "blocked", None
    store.save(current)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(None, None, config), current)
    with pytest.raises(ValueError):
        grant(retained)


def test_stale_and_concurrent_issuance_cannot_replenish(retained):
    config, store, original = retained
    token = preflight(config, original.id, eighth_attempt=True)["state_hash"]
    changed = store.get(original.id)
    changed.usage.append(changed.usage[0].model_copy())
    store.save(changed)
    with pytest.raises(ValueError, match="changed"):
        grant(retained, expected_state_hash=token)
    token = preflight(config, original.id, eighth_attempt=True)["state_hash"]

    def once():
        try:
            return grant(retained, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(result is not None for result in pool.map(lambda _: once(), range(2))) == 1


@pytest.mark.parametrize("mutation", ["audit", "attempt", "usage", "session", "seventh_grant", "remove"])
def test_all_grants_and_prior_evidence_remain_immutable(retained, mutation):
    _, store, original = retained
    grant(retained)
    current = store.get(original.id)
    if mutation == "audit":
        current.planning.eighth_attempt.approval_text = "Changed approval"
    elif mutation == "attempt":
        current.planning.attempts[-1].error = "Changed failure"
    elif mutation == "usage":
        current.usage.clear()
    elif mutation == "session":
        current.id = "different-session"
    elif mutation == "seventh_grant":
        current.planning.seventh_attempt.reason = "Changed reason"
    else:
        current.planning.eighth_attempt = None
    with pytest.raises(ValueError):
        store.save(current)


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
    assert current.planning.eighth_attempt.status == expected_status
    assert service.attempt_limit(current) == (7 if action == "correction" else 8)
    with pytest.raises(ValueError):
        grant(retained)


@pytest.mark.parametrize("mutation", ["id", "hash", "history", "status", "prior_grant"])
def test_contract_binds_seventh_grant_and_seven_attempts(retained, mutation):
    _, store, original = retained
    grant(retained)
    raw = store.get(original.id).model_dump(mode="json", round_trip=True)
    eighth = raw["planning"]["eighth_attempt"]
    if mutation == "id":
        eighth["seventh_attempt_id"] = "another-grant"
    elif mutation == "hash":
        eighth["seventh_attempt_hash"] = "e" * 64
    elif mutation == "history":
        eighth["prior_attempt_hashes"][-1] = "e" * 64
    elif mutation == "status":
        eighth["status"] = "consumed"
    else:
        raw["planning"]["seventh_attempt"] = None
    with pytest.raises(ValueError):
        Session.model_validate(raw)


def test_failed_write_cannot_leave_a_grant(retained):
    _, store, original = retained
    with store.connect() as db:
        db.execute("""CREATE TRIGGER deny_eighth BEFORE UPDATE ON sessions
            WHEN json_extract(NEW.state, '$.planning.eighth_attempt') IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        grant(retained)
    assert store.get(original.id).planning.eighth_attempt is None


@pytest.mark.parametrize("granted", [False, True])
def test_storage_blocks_ungranted_eighth_and_any_ninth(retained, granted):
    _, store, original = retained
    if granted:
        grant(retained)
    current = store.get(original.id)
    current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 8}))
    if granted:
        current.planning.eighth_attempt.status = "consumed"
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 9}))
    with pytest.raises(ValueError):
        store.save(current)


def test_api_and_operator_redact_grant_and_reject_browser_issuance(retained, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, original = retained
    monkeypatch.setattr(command, "Settings", lambda: config)
    monkeypatch.setattr(command, "require_server_stopped", lambda: None)
    approval, output = tmp_path / "approval.txt", tmp_path / "report.json"
    approval.write_text("you can run an eigth attempt PRIVATE EIGHTH APPROVAL", encoding="utf-8")
    args = ["--session-id", original.id, "--output", str(output), "--eighth-attempt"]
    assert command.main(args) == 0
    token = json.loads(output.read_text())["state_hash"]
    args += ["--issue", "--expected-state-hash", token, "--approval-file", str(approval),
             "--reason", "Apply seven-attempt review", "--implementation-commit", "f" * 40]
    assert command.main(args) == 0 and command.main(args) == 1
    public = capsys.readouterr().out + output.read_text()
    assert original.id not in public and "PRIVATE EIGHTH APPROVAL" not in public
    with TestClient(create_app(config)) as client:
        detail = client.get(f"/api/sessions/{original.id}/plan").json()
        assert detail["attempt_limit"] == 8 and "eighth_attempt" not in detail["planning"]
        response = client.post(f"/api/sessions/{original.id}/plan", json={"eighth_attempt": {}})
        assert response.status_code == 422
    assert "eighth_attempt" not in public_session(store.get(original.id))["planning"]


@pytest.mark.parametrize("mutation", ["mode", "limit", "running", "unapproved", "revision", "success"])
def test_issuance_requires_current_approved_seven_failure_state(retained, mutation):
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
    assert not preflight(config, original.id, eighth_attempt=True)["eligible"]
    with pytest.raises(ValueError):
        grant(retained)


@pytest.mark.parametrize("mutation", ["remove", "replenish", "identity"])
async def test_consumed_eighth_cannot_be_removed_or_reidentified(retained, mutation):
    config, store, original = retained
    grant(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    if mutation == "remove":
        current.planning.attempts.pop()
        current.planning.eighth_attempt.status = "granted"
    elif mutation == "replenish":
        current.planning.eighth_attempt = None
    else:
        current.planning.attempts[-1].plan_id = "different-plan"
    with pytest.raises(ValueError):
        store.save(current)
