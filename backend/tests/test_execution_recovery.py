import sqlite3

import pytest

from backend.app.execution.store import ExecutionStore
from backend.app.store import Store
from backend.tests.test_codex_worker import approve_package, fixture
from backend.tests.test_execution_store import run


def test_v1_database_migration_preserves_attempt_identity_and_evidence(tmp_path):
    path = str(tmp_path / "old.db")
    sessions = Store(path)
    original = run()
    original.evidence = {"synthetic": "retained"}
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE execution_runs (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
            "package_id TEXT NOT NULL, plan_hash TEXT NOT NULL, status TEXT NOT NULL, "
            "state TEXT NOT NULL, UNIQUE(session_id,plan_hash,package_id))"
        )
        db.execute(
            "INSERT INTO execution_runs VALUES(?,?,?,?,?,?)",
            (
                original.id,
                original.session_id,
                original.package_id,
                original.plan.content_hash,
                original.status,
                original.model_dump_json(),
            ),
        )
    reopened = ExecutionStore(sessions)
    assert reopened.get(original.id) == original
    assert reopened.get(original.id).phase_attempt == 1
    assert ExecutionStore(sessions).get(original.id).evidence == original.evidence


@pytest.mark.parametrize(
    "scenario,expected",
    [("reconcile_only", "verifying"), ("missing_turn", "blocked"), ("running", "blocked")],
)
async def test_startup_reads_existing_thread_without_duplicate_dispatch(tmp_path, scenario, expected):
    import sys

    from backend.app.codex.client import Client
    from backend.app.codex.transport import Transport
    from backend.tests.test_codex_worker import FAKE

    session, document, executor = fixture(tmp_path, "artifact")
    await approve_package(session, document, executor)
    saved = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[saved.id]
    executor.set(saved.id, status="running")
    inspected = []

    async def factory(current):
        inspected.append((current.thread_id, current.turn_id))
        transport = Transport([sys.executable, "-u", str(FAKE), scenario], cwd=current.worktree)
        await transport.start()
        return Client(transport)

    executor.factory = factory
    await executor.recover()
    result = executor.runs.get(saved.id)
    assert inspected == [("synthetic-thread", "synthetic-turn")]
    assert result.status == expected
    assert result.turn_status == (
        "completed"
        if scenario == "reconcile_only"
        else "unknown"
        if scenario == "missing_turn"
        else "inProgress"
    )
    assert len(executor.runs.list(session.id)) == 1
    if scenario != "reconcile_only":
        with pytest.raises(ValueError):
            executor.repair_phase(session, saved.plan, "P1", None)
    await executor.close()


async def test_failed_interrupt_and_correction_cannot_resurrect_dispatch(tmp_path):
    from backend.app.codex.protocol import CodexError

    session, document, executor = fixture(tmp_path, "hang")
    await approve_package(session, document, executor)
    saved = executor.start(session, session.planning.approval, "P1-W1")
    import asyncio

    for _ in range(200):
        if executor.runs.get(saved.id).turn_id:
            break
        await asyncio.sleep(0.02)
    client = executor.clients[saved.id]

    async def fail(*args):
        raise CodexError("Synthetic interruption failure")

    client.interrupt = fail
    await executor.invalidate(session.id)
    with pytest.raises(CodexError):
        await executor.reconcile(session.id, saved.id)
    assert executor.runs.get(saved.id).stale
    assert executor.runs.get(saved.id).status == "blocked"
    await executor.recover()
    assert executor.runs.get(saved.id).stale
    await executor.close()


async def test_cancelled_run_can_be_inspected_without_resuming_or_replacing_turn(tmp_path):
    session, document, executor = fixture(tmp_path, "artifact")
    await approve_package(session, document, executor)
    saved = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[saved.id]
    await executor.cancel(session.id, saved.id)
    executor.set(saved.id, turn_status="unknown")
    result = await executor.reconcile(session.id, saved.id)
    assert result.status == "cancelled" and result.cancel_requested
    assert result.turn_status == "completed"
    assert len(executor.runs.list(session.id)) == 1
    await executor.close()


async def test_phase_three_review_is_upgraded_without_running_any_worker(tmp_path):
    from backend.tests.test_phase_review import ready

    session, _, executor, phase = await ready(tmp_path)
    executor.runs.patch_phase(phase, lambda p: setattr(p, "review_hash", None))
    await executor.recover()
    restored = executor.runs.phase(session.id, phase.plan.content_hash, "P1")
    assert restored.status == "awaiting_phase_review"
    assert restored.review_hash == phase.review_hash
    assert len(executor.runs.list(session.id)) == 2
    await executor.close()
