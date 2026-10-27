from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.execution.contracts import Run
from backend.app.execution.scheduler import Scheduler
from backend.app.execution.store import ExecutionStore
from backend.app.planning.contracts import PhaseProposal, PlanApproval
from backend.app.planning.validation import accept_phase
from backend.app.store import Store
from backend.tests.planning_fixtures import package, phase
from backend.tests.test_codex_worker import fixture
from backend.tests.test_plan_validation import plan


def setup(tmp_path, capacity=2):
    session, document = plan()
    store = ExecutionStore(Store(str(tmp_path / "state.db")))
    scheduler = Scheduler(store, capacity=capacity, global_capacity=2)
    return session, document, store, scheduler


def identity(document):
    return dict(
        plan_id=document.id,
        revision=document.revision,
        content_hash=document.content_hash,
        requirements_revision=document.requirements_revision,
    )


def test_dependency_needs_integration_and_successor_phase_needs_acceptance(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    assert [p.id for p in scheduler.eligible(session.id, document, "P1")] == ["P1-W1"]
    record = store.claim(Run(session_id=session.id, plan=identity(document), package_id="P1-W1"))
    store.patch(record.id, lambda r: setattr(r, "status", "verifying"))
    assert not scheduler.eligible(session.id, document, "P1")
    with pytest.raises(ValueError, match="accepted"):
        scheduler.eligible(session.id, document, "P2")


def test_claims_are_atomic_across_scheduler_instances_and_apply_global_capacity(tmp_path):
    session, document, store, scheduler = setup(tmp_path, capacity=1)
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    second = first.model_copy(update={"id": "second", "package_id": "P1-W2"})

    def claim(record):
        try:
            scheduler.claim(record, [record.package_id], [record.package_id])
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(claim, [first, second])) == 1
    assert len(store.list(session.id)) == 1


def test_ancestor_paths_interface_claims_and_phase_failure_block_new_dispatch(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    scheduler.claim(first, ["src"], ["shared:v1"])
    other = first.model_copy(update={"id": "second", "package_id": "P1-W2"})
    for paths, interfaces in [(["SRC/child.py"], []), (["api"], ["shared:v1"])]:
        with pytest.raises(ValueError, match="conflict"):
            scheduler.claim(other, paths, interfaces)
    store.patch(first.id, lambda r: setattr(r, "status", "blocked"))
    with pytest.raises(ValueError, match="blocked"):
        scheduler.claim(other, ["api"], [])


def test_two_disjoint_claims_fit_but_third_and_other_phase_do_not(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    scheduler.claim(first, ["ui"], [])
    scheduler.claim(first.model_copy(update={"id": "second", "package_id": "P1-W2"}), ["api"], [])
    with pytest.raises(ValueError):
        scheduler.claim(first.model_copy(update={"id": "third", "package_id": "P1-W3"}), ["docs"], [])
    with pytest.raises(ValueError):
        scheduler.claim(first.model_copy(update={"id": "next", "package_id": "P2-W1"}), ["tests"], [])


def test_limits_and_resume_do_not_duplicate_claim(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    with pytest.raises(ValueError, match="allowance"):
        scheduler.claim(first, ["ui"], [], allowance=False)
    assert not store.list(session.id)
    scheduler.claim(first, ["ui"], [])
    with pytest.raises(ValueError):
        Scheduler(store, capacity=2, global_capacity=2).claim(first, ["ui"], [])


def test_invalid_capacity_is_rejected(tmp_path):
    _, _, store, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        Scheduler(store, capacity=3, global_capacity=2)


def test_same_phase_dependency_and_interface_wait_for_integrated_commit(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    document.phases[0] = accept_phase(
        PhaseProposal.model_validate(
            phase(packages=[package("contracts", "contracts"), package("api", "api", ["contracts"])])
        ),
        document.outline,
        0,
    )
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    scheduler.claim(first, ["contracts"], [])
    store.patch(first.id, lambda r: setattr(r, "status", "verifying"))
    assert not scheduler.eligible(session.id, document, "P1")

    def integrate(r):
        r.status, r.integrated_commit = "integrated", "a" * 40

    store.patch(first.id, integrate)
    assert [p.id for p in scheduler.eligible(session.id, document, "P1")] == ["P1-W2"]


async def test_failure_interrupts_other_worker_and_stale_approval_cannot_dispatch(tmp_path):
    import asyncio

    session, document, executor = fixture(tmp_path, "hang")
    document.id = "two-workers"
    document.phases[0] = accept_phase(
        PhaseProposal.model_validate(
            phase(packages=[package("contracts", "contracts"), package("api", "api")])
        ),
        document.outline,
        0,
    )
    identity_ = PlanApproval.model_validate(identity(document))
    session.planning.active = session.planning.approval = identity_
    executor.sessions.save(session)
    executor.sessions.save_plan(session.id, document)
    executor.scheduler.capacity = 2
    first = executor.start(session, identity_, "P1-W1")
    second = executor.start(session, identity_, "P1-W2")
    for _ in range(300):
        if all(executor.runs.get(r.id).turn_id for r in (first, second)):
            break
        await asyncio.sleep(0.02)
    assert all(executor.runs.get(r.id).turn_id for r in (first, second))
    await executor.cancel(session.id, first.id)
    await asyncio.wait_for(asyncio.gather(*executor.tasks.values(), return_exceptions=True), 5)
    assert executor.runs.get(second.id).status == "blocked"
    assert executor.runs.get(second.id).cancel_requested
    session.revision += 1
    with pytest.raises(ValueError, match="approved"):
        executor.start(session, identity_, "P1-W2")
    await executor.close()


def test_readers_of_integrated_interface_can_share_capacity_but_writers_conflict(tmp_path):
    session, document, store, scheduler = setup(tmp_path)
    first = Run(session_id=session.id, plan=identity(document), package_id="P1-W1")
    scheduler.claim(first, ["ui"], ["read:shared@v1"])
    other = first.model_copy(update={"id": "second", "package_id": "P1-W2"})
    with pytest.raises(ValueError, match="conflict"):
        scheduler.claim(other, ["api"], ["write:shared@v1"])
    scheduler.claim(other, ["api"], ["read:shared@v1"])
    assert len(store.list(session.id)) == 2
