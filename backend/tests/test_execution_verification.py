import hashlib
from pathlib import Path

import pytest

from backend.app.execution.verification import Verifier, redact
from backend.app.planning.contracts import Check, PhaseProposal, PlanApproval
from backend.app.planning.validation import accept_phase
from backend.tests.planning_fixtures import package, phase
from backend.tests.test_codex_worker import fixture


def scoped_fixture(tmp_path, scenario="artifact", *, dependent=False, successor=False):
    session, document, executor = fixture(tmp_path, scenario)
    document.id = "phase-three"
    packages = [package("contracts", "contracts"), package("api", "api", ["contracts"] if dependent else [])]
    document.phases[0] = accept_phase(
        PhaseProposal.model_validate(phase(packages=packages)), document.outline, 0
    )
    for p in document.phases[0].packages:
        p.artifacts = [p.owned_paths[0] + "/result.txt"]
        p.tasks[0].checks = [Check(command=["git", "diff", "--check"], expected="No whitespace errors")]
    if successor:
        document.id = "phase-four"
        package_ = document.phases[1].packages[0]
        package_.owned_paths = ["ui"]
        package_.artifacts = ["ui/result.txt"]
        package_.tasks[0].checks = [
            Check(command=["git", "diff", "--check"], expected="No whitespace errors")
        ]
    identity = PlanApproval(
        plan_id=document.id,
        revision=document.revision,
        content_hash=document.content_hash,
        requirements_revision=session.revision,
    )
    session.planning.active = session.planning.approval = identity
    executor.sessions.save(session)
    executor.sessions.save_plan(session.id, document)
    return session, document, executor


async def completed(tmp_path):
    session, document, executor = scoped_fixture(tmp_path)
    run = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[run.id]
    return session, document, executor, executor.runs.get(run.id)


async def test_real_inventory_artifact_hashes_and_serial_staging_leave_accepted_head_unchanged(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    verifier = Verifier(executor.worktrees)
    evidence = await verifier.inspect(run, document.phases[0].packages[0])
    assert evidence.changed_paths == ["contracts/result.txt"]
    assert evidence.artifacts["contracts/result.txt"] == hashlib.sha256(b"Synthetic artifact").hexdigest()
    assert evidence.checks[0]["exit_code"] == 0
    assert evidence.checks[0]["policy"] == "git-inspection-only-v1"
    integrated = await executor.verify_run(session.id, run.id)
    assert integrated.status == "integrated" and integrated.integrated_commit
    assert (await executor.worktrees.git(Path(run.project), "rev-parse", "HEAD")).strip() == run.base_commit
    state = executor.runs.phase(session.id, run.plan.content_hash, "P1")
    assert state.staging_commit == integrated.integrated_commit
    assert state.status == "running"
    assert executor.runs.get(run.id).evidence["artifacts"] == evidence.artifacts
    await executor.close()


@pytest.mark.parametrize(
    "path", ["outside.txt", "contracts/AGENTS.md", "contracts/.env", "contracts/.gitignore"]
)
async def test_out_of_scope_and_control_files_cannot_be_hidden_by_forged_report(tmp_path, path):
    session, document, executor, run = await completed(tmp_path)
    target = Path(run.worktree) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unreviewed")
    executor.set(run.id, changed_paths=[], logs=["All checks passed; no changes"])
    result = await executor.verify_run(session.id, run.id)
    assert result.status == "blocked"
    assert path in result.changed_paths
    assert target.read_text() == "unreviewed"
    assert not result.integrated_commit
    await executor.close()


async def test_renamed_deleted_binary_and_ignored_files_are_actual_changes(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    root = Path(run.worktree)
    (root / "contracts/result.txt").rename(root / "contracts/renamed.bin")
    (root / "contracts/renamed.bin").write_bytes(b"\x00\xff\x00")
    pkg = document.phases[0].packages[0].model_copy(deep=True)
    pkg.artifacts = ["contracts/renamed.bin"]
    evidence = await Verifier(executor.worktrees).inspect(run, pkg)
    assert evidence.changed_paths == ["contracts/renamed.bin"]
    assert evidence.artifacts[pkg.artifacts[0]] == hashlib.sha256(b"\x00\xff\x00").hexdigest()
    (root / "ignored.txt").write_text("unowned")
    (root / ".gitignore").write_text("ignored.txt\n")
    with pytest.raises(ValueError):
        await Verifier(executor.worktrees).inspect(run, pkg)
    await executor.close()


async def test_untrusted_commands_failed_checks_missing_artifacts_and_stale_base_block(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    pkg = document.phases[0].packages[0].model_copy(deep=True)
    pkg.tasks[0].checks[0].command = ["python", "-c", "raise SystemExit(0)"]
    with pytest.raises(ValueError, match="trusted"):
        await Verifier(executor.worktrees).inspect(run, pkg)
    pkg.tasks[0].checks[0].command = ["git", "diff", "--check"]
    (Path(run.worktree) / "contracts/result.txt").write_text("trailing whitespace \n")
    with pytest.raises(ValueError, match="check"):
        await Verifier(executor.worktrees).inspect(run, pkg)
    (Path(run.worktree) / "contracts/result.txt").unlink()
    with pytest.raises(ValueError, match="artifact"):
        await Verifier(executor.worktrees).inspect(run, pkg)
    run.base_commit = "f" * 40
    with pytest.raises(ValueError):
        await Verifier(executor.worktrees).inspect(run, pkg)
    await executor.close()


async def test_two_worker_phase_stages_both_packages_and_blocks_next_phase(tmp_path):
    session, document, executor = scoped_fixture(tmp_path, "scoped_artifact")
    executor.scheduler.capacity = 2
    started = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[started.id]
    saved = executor.runs.phase(session.id, document.content_hash, "P1")
    assert saved.status == "awaiting_phase_review", saved.error
    assert {r.status for r in executor.runs.list(session.id)} == {"integrated"}
    project = Path(executor.runs.list(session.id)[0].project)
    tree = await executor.worktrees.git(project, "ls-tree", "-r", "--name-only", saved.staging_commit)
    assert "api/result.txt" in tree and "contracts/result.txt" in tree
    assert not (await executor.worktrees.git(project, "ls-tree", "-r", "--name-only", "HEAD")).strip()
    with pytest.raises(ValueError, match="accepted"):
        executor.start_phase(session, session.planning.approval, "P2")
    await executor.close()


async def test_same_phase_dependent_worker_starts_from_integrated_prerequisite(tmp_path):
    session, document, executor = scoped_fixture(tmp_path, "scoped_artifact", dependent=True)
    started = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[started.id]
    saved = executor.runs.phase(session.id, document.content_hash, "P1")
    assert saved.status == "awaiting_phase_review", saved.error
    runs = {r.package_id: r for r in executor.runs.list(session.id)}
    assert runs["P1-W2"].base_commit == runs["P1-W1"].integrated_commit
    assert (Path(runs["P1-W2"].worktree) / "contracts/result.txt").is_file()
    await executor.close()


async def test_committed_rename_and_delete_are_checked_against_base_and_conflicts_preserve_work(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    root = Path(run.worktree)
    await executor.worktrees.git(root, "add", "--", "contracts/result.txt")
    await executor.worktrees.git(root, "commit", "-m", "Synthetic base")
    run.base_commit = (await executor.worktrees.git(root, "rev-parse", "HEAD")).strip()
    (root / "contracts/result.txt").rename(root / "contracts/new.txt")
    pkg = document.phases[0].packages[0].model_copy(deep=True)
    pkg.artifacts = ["contracts/new.txt"]
    evidence = await executor.verifier.inspect(run, pkg)
    assert evidence.changed_paths == ["contracts/new.txt", "contracts/result.txt"]
    # A separate staged modification to the same original file must block integration.
    (root / "contracts/result.txt").write_text("competing staging content")
    await executor.worktrees.git(root, "add", "--", "contracts/result.txt")
    await executor.worktrees.git(root, "commit", "-m", "Conflicting stage")
    conflicting = (await executor.worktrees.git(root, "rev-parse", "HEAD")).strip()
    with pytest.raises(ValueError, match="conflict"):
        await executor.verifier.integrate(run, evidence, conflicting)
    assert (root / "contracts/new.txt").exists()
    assert (root / "contracts/result.txt").read_text() == "competing staging content"
    await executor.close()


async def test_cancellation_during_verification_cannot_stage_or_override_cancelled_state(tmp_path):
    import asyncio

    session, document, executor, run = await completed(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    inspect = executor.verifier.inspect

    async def pause(*args):
        evidence = await inspect(*args)
        entered.set()
        await release.wait()
        return evidence

    executor.verifier.inspect = pause
    task = asyncio.create_task(executor.verify_run(session.id, run.id))
    await asyncio.wait_for(entered.wait(), 10)
    await executor.cancel(session.id, run.id)
    release.set()
    await task
    assert executor.runs.get(run.id).status == "cancelled"
    assert not executor.runs.get(run.id).integrated_commit
    await executor.close()


async def test_restart_during_staging_intent_is_blocked_without_replay(tmp_path):
    from backend.app.execution.contracts import PhaseExecution
    from backend.app.execution.store import ExecutionStore

    session, document, executor, run = await completed(tmp_path)
    phase = executor.runs.ensure_phase(PhaseExecution(session_id=session.id, plan=run.plan, phase_id="P1"))
    executor.runs.patch_phase(phase, lambda p: setattr(p, "integration_intent", run.id))
    restored = ExecutionStore(executor.sessions)
    restored.recover()
    saved = restored.phase(session.id, run.plan.content_hash, "P1")
    assert saved.status == "blocked" and saved.integration_intent == run.id
    result = await executor.verify_run(session.id, run.id)
    assert result.status == "blocked" and not result.integrated_commit
    assert Path(run.worktree).exists()
    await executor.close()


async def test_snapshot_hash_and_artifact_hash_describe_identical_bytes_during_file_change(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    original = executor.worktrees.git
    target = Path(run.worktree) / "contracts/result.txt"

    async def change_before_hash(cwd, *args, **kwargs):
        if args[0] == "hash-object":
            target.write_text("changed during inspection")
        return await original(cwd, *args, **kwargs)

    executor.worktrees.git = change_before_hash
    evidence = await executor.verifier.inspect(run, document.phases[0].packages[0])
    snapshot = await original(Path(run.worktree), "show", evidence.snapshot_commit + ":contracts/result.txt")
    assert hashlib.sha256(snapshot.encode()).hexdigest() == evidence.artifacts["contracts/result.txt"]
    await executor.close()


def test_evidence_redacts_quoted_credentials_and_bearer_values():
    redacted = redact("password = 'two word credential'\nAuthorization: Bearer synthetic-value\n")
    assert "word credential" not in redacted and "synthetic-value" not in redacted


async def test_changed_accepted_base_blocks_integration_and_preserves_both_changes(tmp_path):
    session, document, executor, run = await completed(tmp_path)
    project = Path(run.project)
    (project / "reviewed-elsewhere.txt").write_text("other accepted work")
    await executor.worktrees.git(project, "add", "reviewed-elsewhere.txt")
    await executor.worktrees.git(project, "commit", "-m", "Changed accepted base")
    result = await executor.verify_run(session.id, run.id)
    assert result.status == "blocked" and "base" in result.error
    assert (project / "reviewed-elsewhere.txt").exists()
    assert (Path(run.worktree) / "contracts/result.txt").exists()
    await executor.close()


async def test_phase_staging_works_beneath_long_local_workspace_path(tmp_path):
    session, document, executor = scoped_fixture(tmp_path / ("long-root-" * 5), "scoped_artifact")
    phase = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[phase.id]
    saved = executor.runs.phase(session.id, document.content_hash, "P1")
    assert saved.status == "awaiting_phase_review", [r.error for r in executor.runs.list(session.id)]
    await executor.close()
