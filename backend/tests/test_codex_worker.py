import asyncio
import sys
from pathlib import Path

import pytest

from backend.app.codex.client import Client
from backend.app.codex.transport import Transport
from backend.app.execution.worker import Executor
from backend.app.planning.contracts import PlanApproval
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.test_plan_validation import plan

FAKE = Path(__file__).parent / "fixtures/codex/fake_server.py"


def fixture(tmp_path, scenario="success"):
    session, document = plan()
    session.mode = document.mode = "live"
    document.phases[0].packages[0].owned_paths = ["contracts"]
    identity = PlanApproval(
        plan_id=document.id,
        revision=document.revision,
        content_hash=document.content_hash,
        requirements_revision=session.revision,
    )
    session.planning.status = "approved"
    session.planning.active = session.planning.approval = identity
    settings = Settings(
        mode="live",
        allow_codex_execution=True,
        database_path=str(tmp_path / "state.db"),
        codex_project_root=str(tmp_path / "projects"),
        codex_worktree_root=str(tmp_path / "workers"),
    )
    store = Store(settings.database_path)
    store.save(session)
    store.save_plan(session.id, document)

    async def factory(run):
        transport = Transport([sys.executable, "-u", str(FAKE), scenario], cwd=run.worktree)
        await transport.start()
        return Client(transport)

    executor = Executor(settings, store, factory)
    return session, document, executor


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("success", "verifying"),
        ("artifact", "verifying"),
        ("failed", "blocked"),
        ("lost_start", "blocked"),
        ("unknown_approval", "blocked"),
        ("outside", "blocked"),
    ],
)
async def test_one_package_lifecycle_preserves_ids_and_never_accepts_phase(tmp_path, scenario, status):
    session, document, executor = fixture(tmp_path, scenario)
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    await executor.tasks[run.id]
    saved = executor.runs.get(run.id)
    assert saved.status == status
    assert Path(saved.worktree).is_dir()
    assert saved.thread_id == "synthetic-thread"
    if scenario == "lost_start":
        assert saved.turn_id is None and saved.dispatch_intent == "turn/start"
    else:
        assert saved.turn_id == "synthetic-turn"
    if scenario in {"success", "artifact", "failed"}:
        assert saved.token_usage["totalTokens"] == 17
    with pytest.raises(ValueError):
        executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    await executor.close()


async def test_known_completed_turn_is_reconciled_without_starting_another_turn(tmp_path):
    session, document, executor = fixture(tmp_path, "artifact")
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    await executor.tasks[run.id]
    executor.set(run.id, status="blocked", error="Synthetic reconnect")

    async def recovery(saved):
        transport = Transport([sys.executable, "-u", str(FAKE), "reconcile_only"], cwd=saved.worktree)
        await transport.start()
        return Client(transport)

    executor.factory = recovery
    await executor.reconcile(session.id, run.id)
    assert executor.runs.get(run.id).status == "verifying"
    assert (
        Path(executor.runs.get(run.id).worktree) / "contracts/result.txt"
    ).read_text() == "Synthetic artifact"
    await executor.close()


async def test_permission_is_durable_and_requires_matching_generation(tmp_path):
    session, document, executor = fixture(tmp_path, "approval")
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    for _ in range(100):
        saved = executor.runs.get(run.id)
        if saved.approvals:
            break
        await asyncio.sleep(0.02)
    request = saved.approvals[0]
    with pytest.raises(ValueError):
        await executor.decide(session.id, run.id, request.id, "accept", "wrong")
    await executor.decide(session.id, run.id, request.id, "accept", saved.generation)
    await executor.tasks[run.id]
    assert executor.runs.get(run.id).approvals[0].status == "accept"
    assert executor.runs.get(run.id).status == "verifying"
    await executor.close()


async def test_cancellation_preserves_work_and_closes_owned_process(tmp_path):
    session, document, executor = fixture(tmp_path, "hang")
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    for _ in range(100):
        if executor.runs.get(run.id).turn_id:
            break
        await asyncio.sleep(0.02)
    await executor.cancel(session.id, run.id)
    assert executor.runs.get(run.id).status == "cancelled"
    assert Path(executor.runs.get(run.id).worktree).is_dir()
    await executor.close()


async def test_recovery_without_turn_id_remains_blocked_and_does_not_spawn(tmp_path):
    session, document, executor = fixture(tmp_path, "lost_start")
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    await executor.tasks[run.id]
    await executor.reconcile(session.id, run.id)
    assert executor.runs.get(run.id).status == "blocked"
    assert executor.runs.get(run.id).turn_id is None
    await executor.close()


async def test_cancellation_during_change_inventory_cannot_turn_into_success(tmp_path):
    session, document, executor = fixture(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    changed = executor.worktrees.changed_paths

    async def pause(*args):
        entered.set()
        await release.wait()
        return await changed(*args)

    executor.worktrees.changed_paths = pause
    run = executor.start(session, session.planning.approval, document.phases[0].packages[0].id)
    await asyncio.wait_for(entered.wait(), 5)
    connection = executor.clients[run.id]
    interrupt = connection.interrupt

    async def interrupt_after_inventory(*args):
        release.set()
        await asyncio.sleep(0.1)
        return await interrupt(*args)

    connection.interrupt = interrupt_after_inventory
    await executor.cancel(session.id, run.id)
    assert executor.runs.get(run.id).status == "cancelled"
    await executor.close()
