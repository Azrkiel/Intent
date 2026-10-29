"""A separately approved fourth attempt cannot replenish the original extension."""

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
from backend.tests.test_planning_extension import grant
from backend.tests.test_planning_extension import setup as extension_setup  # noqa: F401


@pytest.fixture
def retained(request):
    setup = request.getfixturevalue("extension_setup")
    config, store, original = setup
    grant(setup)
    session = store.get(original.id)
    session.planning.extension.status = "consumed"
    session.planning.attempts.append(
        PlanAttempt(
            plan_id=session.planning.attempts[0].plan_id, revision=3,
            requirements_revision=session.revision, passes=["planner:outline"],
            error="Retained third-attempt identity mismatch",
        )
    )
    session.usage.append(session.usage[0].model_copy())
    store.save(session)
    return config, store, session


def qualify(retained, **changes):
    config, _, original = retained
    args = dict(
        expected_state_hash=preflight(config, original.id, requalification=True)["state_hash"],
        approval_text="yea, that's fine. PRIVATE FOURTH APPROVAL",
        reason="Qualify exact-reference and runner-policy request fixes",
        implementation_commit="b" * 40,
    )
    return issue(config, original.id, requalification=True, **(args | changes))


async def collect(service, session):
    return [event async for event in service.generate(session)]


def test_requalification_preflight_is_read_only_and_default_stays_exhausted(retained):
    config, store, original = retained
    before = store.get(original.id).model_dump_json(round_trip=True)
    assert preflight(config, original.id)["eligible"] is False
    report = preflight(config, original.id, requalification=True)
    assert report["eligible"] and report["attempt_limit"] == 3
    assert report["requalification_status"] is None
    assert original.id not in json.dumps(report)
    assert store.get(original.id).model_dump_json(round_trip=True) == before


async def test_fourth_attempt_preserves_history_and_requires_plan_approval(retained):
    config, store, original = retained
    assert qualify(retained)["attempt_limit"] == 4
    session = store.get(original.id)
    assert session.planning.extension == original.planning.extension
    events = await collect(PlanningService(store, DemoModels(), config), session)
    restored = store.get(original.id)
    assert events[-1]["type"] == "plan_ready"
    assert restored.planning.active.revision == 4
    assert restored.planning.active.plan_id == original.planning.attempts[0].plan_id
    assert restored.planning.approval is None
    assert restored.planning.requalification.status == "consumed"
    assert restored.planning.extension == original.planning.extension
    assert restored.planning.attempts[:3] == original.planning.attempts
    assert restored.usage[:len(original.usage)] == original.usage
    restored.planning.status, restored.planning.active = "blocked", None
    store.save(restored)
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(store, None, config), restored)
    with pytest.raises(ValueError):
        qualify(retained)


@pytest.mark.parametrize("failure", ["schema", "semantic", "passes", "budget"])
async def test_failed_fourth_attempt_is_consumed_and_cannot_retry(retained, failure):
    config, store, original = retained
    qualify(retained)
    if failure == "passes":
        config.planning_max_passes = 1
    if failure == "budget":
        config.session_budget_usd = 0.01

    class Failing(DemoModels):
        async def call(self, current, role, *args):
            if failure == "schema":
                current.usage.append(current.usage[0].model_copy())
                raise ModelError("Invalid JSON after one repair retry")
            result = await super().call(current, role, *args)
            if failure == "semantic" and role == "planner:verify":
                result.reviewed_statement_ids = []
            return result

    provider = LiveModels(config) if failure == "budget" else Failing()
    session = store.get(original.id)
    events = await collect(PlanningService(store, provider, config), session)
    restored = store.get(original.id)
    assert events[-1]["type"] == "plan_error"
    assert restored.planning.requalification.status == "consumed"
    assert restored.planning.active is restored.planning.approval is None
    assert restored.planning.extension == original.planning.extension
    assert restored.planning.attempts[:3] == original.planning.attempts
    assert restored.usage[:len(original.usage)] == original.usage
    if failure == "budget":
        assert provider.client is None
    with pytest.raises(ValueError, match="allowance"):
        await collect(PlanningService(store, None, config), restored)


def test_duplicate_and_concurrent_issuance_never_adds_more_allowance(retained):
    config, store, original = retained
    token = preflight(config, original.id, requalification=True)["state_hash"]

    def once():
        try:
            return qualify(retained, expected_state_hash=token)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(value is not None for value in pool.map(lambda _: once(), range(2))) == 1
    assert store.get(original.id).planning.extension == original.planning.extension
    with pytest.raises(ValueError):
        qualify(retained)


def test_stale_issuance_rolls_back_and_stale_session_cannot_erase_grant(retained):
    config, store, original = retained
    token = preflight(config, original.id, requalification=True)["state_hash"]
    changed = store.get(original.id)
    changed.usage.append(changed.usage[0].model_copy())
    store.save(changed)
    with pytest.raises(ValueError, match="changed"):
        qualify(retained, expected_state_hash=token)
    assert store.get(original.id).planning.requalification is None
    qualify(retained)
    with pytest.raises(ValueError, match="requalification"):
        store.save(changed)


def test_failed_database_write_cannot_leave_a_grant(retained):
    _, store, original = retained
    with store.connect() as db:
        db.execute("""CREATE TRIGGER deny_grant BEFORE UPDATE ON sessions
            WHEN json_extract(NEW.state, '$.planning.requalification') IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        qualify(retained)
    assert store.get(original.id).planning.requalification is None


async def test_concurrent_generation_reserves_and_dispatches_only_one_fourth_attempt(retained):
    config, store, original = retained
    qualify(retained)
    first, stale = store.get(original.id), store.get(original.id)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Paused(DemoModels):
        async def call(self, session, role, *args):
            calls.append(role)
            if role == "planner:outline":
                saved = store.get(session.id)
                assert saved.planning.requalification.status == "consumed"
                assert len(saved.planning.attempts) == 4
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


async def test_correction_invalidates_unused_qualification_but_preserves_original_extension(retained):
    config, store, original = retained
    qualify(retained)
    session = store.get(original.id)
    generator = Engine(store, DemoModels()).turn(session, "Use browser storage only")
    await anext(generator)
    await generator.aclose()
    restored = store.get(original.id)
    assert restored.planning.requalification.status == "invalidated"
    assert restored.planning.extension == original.planning.extension
    assert restored.planning.attempts == original.planning.attempts
    assert PlanningService(store, None, config).attempt_limit(restored) == 3
    with pytest.raises(ValueError):
        qualify(retained)


async def test_restart_and_interruption_consume_qualification_without_replay(retained):
    config, store, original = retained
    qualify(retained)
    service = PlanningService(store, None, config)
    generator = service.generate(store.get(original.id))
    await anext(generator)
    store.recover()
    restored = store.get(original.id)
    assert restored.planning.status == "blocked"
    assert restored.planning.requalification.status == "consumed"
    assert restored.planning.attempts[:3] == original.planning.attempts
    with pytest.raises(ValueError, match="allowance"):
        await collect(service, restored)
    await generator.aclose()


@pytest.mark.parametrize("change", ["approval", "extension", "attempt", "usage", "session"])
def test_grant_and_prior_evidence_cannot_be_rewritten(retained, change):
    _, store, original = retained
    qualify(retained)
    current = store.get(original.id)
    if change == "approval":
        current.planning.requalification.approval_text = "Replaced approval"
    elif change == "extension":
        current.planning.extension.approval_text = "Replaced extension"
    elif change == "attempt":
        current.planning.attempts[2].error = "Rewritten failure"
    elif change == "usage":
        current.usage.clear()
    else:
        current.id = "another-session"
    with pytest.raises(ValueError):
        store.save(current)


@pytest.mark.parametrize("change", ["mode", "limit", "running", "unapproved", "revision", "success"])
def test_issuance_requires_the_current_approved_failed_session(retained, change):
    config, store, original = retained
    current = store.get(original.id)
    if change == "mode":
        config.mode = "demo"
    elif change == "limit":
        config.planning_max_attempts = 1
    elif change == "running":
        current.build.status = "running"
    elif change == "unapproved":
        current.approved_revision = None
    elif change == "revision":
        current.revision += 1
        current.approved_revision = current.revision
    else:
        current.planning.attempts[2].error = None
    store.save(current)
    assert preflight(config, original.id, requalification=True)["eligible"] is False
    with pytest.raises(ValueError):
        qualify(retained)


def test_api_shares_the_limit_and_never_exposes_or_accepts_grant_audit(retained):
    config, store, original = retained
    qualify(retained)
    with TestClient(create_app(config)) as client:
        client.app.state.engine.models.call = DemoModels().call
        detail = client.get(f"/api/sessions/{original.id}/plan").json()
        assert detail["attempt_limit"] == 4
        assert "requalification" not in detail["planning"]
        response = client.post(f"/api/sessions/{original.id}/plan", json={"requalification": {}})
        assert response.status_code == 422
        response = client.post(f"/api/sessions/{original.id}/plan", json={})
        assert response.status_code == 200 and '"type": "plan_ready"' in response.text
        assert "PRIVATE FOURTH APPROVAL" not in response.text + json.dumps(detail)
        assert client.get(f"/api/sessions/{original.id}/plan/bundle").status_code == 409
    assert "requalification" not in public_session(store.get(original.id))["planning"]


def test_operator_cli_checks_server_and_redacts_reports(retained, tmp_path, monkeypatch, capsys):
    from backend import planning_extension as command

    config, store, original = retained
    monkeypatch.setattr(command, "Settings", lambda: config)
    checks = []
    monkeypatch.setattr(command, "require_server_stopped", lambda: checks.append(True))
    marker, approval, output = (tmp_path / name for name in ("session.txt", "approval.txt", "report.json"))
    marker.write_text(original.id, encoding="utf-8")
    approval.write_text("PRIVATE FOURTH APPROVAL", encoding="utf-8")
    common = ["--requalify", "--session-id-file", str(marker), "--output", str(output)]
    assert command.main(common) == 0
    token = json.loads(output.read_text())["state_hash"]
    issuance = common + ["--issue", "--expected-state-hash", token, "--approval-file", str(approval),
                         "--reason", "Request contract fixes", "--implementation-commit", "b" * 40]
    assert command.main(issuance) == 0
    assert command.main(issuance) == 1
    assert len(checks) == 2
    public = capsys.readouterr().out + output.read_text()
    assert original.id not in public and "PRIVATE FOURTH APPROVAL" not in public
    assert store.get(original.id).planning.extension == original.planning.extension


@pytest.mark.parametrize("granted", [False, True])
def test_storage_rejects_ungranted_fourth_and_any_fifth_attempt(retained, granted):
    _, store, original = retained
    if granted:
        qualify(retained)
    current = store.get(original.id)
    current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 4}))
    if granted:
        current.planning.requalification.status = "consumed"
        current.planning.attempts.append(current.planning.attempts[-1].model_copy(update={"revision": 5}))
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(original.id).planning.attempts) == 3


@pytest.mark.parametrize("mutation", ["extension_id", "extension_hash", "prior_hash", "status", "remove"])
def test_qualification_contract_binds_the_original_extension_and_all_prior_attempts(retained, mutation):
    _, store, original = retained
    qualify(retained)
    raw = store.get(original.id).model_dump(mode="json", round_trip=True)
    qualification = raw["planning"]["requalification"]
    if mutation == "extension_id":
        qualification["extension_id"] = "another-extension"
    elif mutation == "extension_hash":
        qualification["extension_hash"] = "f" * 64
    elif mutation == "prior_hash":
        qualification["prior_attempt_hashes"][2] = "f" * 64
    elif mutation == "status":
        qualification["status"] = "consumed"
    else:
        raw["planning"]["extension"] = None
    with pytest.raises(ValueError):
        Session.model_validate(raw)


@pytest.mark.parametrize("mutation", ["remove", "replenish", "identity"])
async def test_consumed_fourth_attempt_cannot_be_removed_replenished_or_reidentified(retained, mutation):
    config, store, original = retained
    qualify(retained)
    generator = PlanningService(store, None, config).generate(store.get(original.id))
    await anext(generator)
    await generator.aclose()
    current = store.get(original.id)
    if mutation == "remove":
        current.planning.attempts.pop()
        current.planning.requalification.status = "granted"
    elif mutation == "replenish":
        current.planning.requalification = None
    else:
        current.planning.attempts[3].plan_id = "replacement-plan"
    with pytest.raises(ValueError):
        store.save(current)
    assert len(store.get(original.id).planning.attempts) == 4


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_fourth_attempt_uses_only_existing_model_adapter_repair(retained, repair_succeeds):
    import httpx
    from openai import AsyncOpenAI

    from backend.app.planning.demo import demo_response
    from backend.tests.test_models import completion

    config, store, original = retained
    qualify(retained)
    session = store.get(original.id)
    requests = []
    roles = ["planner:outline", "planner:screen:main", "planner:phase:foundation",
             "planner:phase:implementation", "planner:verify"]

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1 or not repair_succeeds:
            return httpx.Response(200, json=completion("Invalid JSON"))
        payload = json.loads(body["messages"][1]["content"])
        result = demo_response(session, roles[len(requests) - 2], payload)
        return httpx.Response(200, json=completion(json.dumps(result)))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(config, client=client)
    try:
        events = await collect(PlanningService(store, provider, config), session)
    finally:
        await provider.close()
    restored = store.get(original.id)
    assert len(requests) == (6 if repair_succeeds else 2)
    assert len(restored.usage) == len(original.usage) + len(requests)
    assert events[-1]["type"] == ("plan_ready" if repair_succeeds else "plan_error")
    assert restored.planning.requalification.status == "consumed"
    assert restored.planning.approval is None
    assert restored.planning.extension == original.planning.extension
