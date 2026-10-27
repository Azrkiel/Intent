import json
from pathlib import Path

import httpx
import pytest

from backend.app.execution.review import transition
from backend.app.main import create_app
from backend.tests.test_execution_verification import scoped_fixture


async def ready(tmp_path):
    session, document, executor = scoped_fixture(tmp_path, "scoped_artifact")
    phase = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[phase.id]
    phase = executor.runs.phase(session.id, phase.plan.content_hash, "P1")
    assert phase.status == "awaiting_phase_review", phase.error
    return session, document, executor, phase


@pytest.mark.parametrize(
    "kind,states",
    [
        ("run", ["queued", "running", "verifying", "integrated", "blocked", "cancelled"]),
        ("phase", ["running", "verifying", "awaiting_phase_review", "accepted", "blocked", "cancelled"]),
        ("plan", ["draft", "planning", "review_ready", "approved", "blocked", "stale"]),
    ],
)
def test_explicit_transition_matrix(kind, states):
    allowed = {
        "run": {("queued", "running"), ("running", "verifying"), ("verifying", "integrated")},
        "phase": {
            ("running", "verifying"),
            ("verifying", "awaiting_phase_review"),
            ("awaiting_phase_review", "accepted"),
        },
        "plan": {
            ("draft", "planning"),
            ("planning", "review_ready"),
            ("review_ready", "approved"),
            ("blocked", "planning"),
        },
    }[kind]
    terminal = {
        "run": {"integrated", "blocked", "cancelled"},
        "phase": {"accepted", "blocked", "cancelled"},
        "plan": {"stale"},
    }[kind]
    failures = {"blocked", "stale"} if kind == "plan" else {"blocked", "cancelled"}
    for before in states:
        for after in states:
            valid = (
                before == after
                or (before, after) in allowed
                or (before not in terminal and after in failures)
            )
            if valid:
                assert transition(kind, before, after) == after
            else:
                with pytest.raises(ValueError):
                    transition(kind, before, after)


async def test_review_identity_rejects_changed_staging_attempts_checks_and_decisions(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    review = executor.runs.review(phase.review_hash)
    original = review.payload_json
    for field, value in [
        ("staging_commit", "f" * 40),
        ("attempt", 2),
        ("evidence", {**phase.evidence, "checks": []}),
        ("evidence", {**phase.evidence, "decisions": ["Unresolved"]}),
    ]:
        executor.runs.patch_phase(phase, lambda p: setattr(p, field, value))
        with pytest.raises(ValueError):
            await executor.review_phase(session.id, phase.plan, "P1", review.evidence_hash, "accept")
        executor.runs.patch_phase(phase, lambda p: setattr(p, field, getattr(phase, field)))
    assert executor.runs.review(review.evidence_hash).payload_json == original
    assert json.loads(original)["staging_commit"] == phase.staging_commit
    await executor.close()


async def test_accept_promotes_exact_commit_once_and_only_enables_explicit_successor(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    result = await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    assert result.status == "accepted"
    project = await executor.worktrees.owned_project(session.id)
    assert (
        await executor.worktrees.git(project, "rev-parse", "refs/heads/accepted")
    ).strip() == phase.staging_commit
    assert len(executor.runs.list(session.id)) == 2
    again = await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    assert again.status == "accepted"
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "reject")
    document = executor.sessions.get_plan(session.id, phase.plan.plan_id, phase.plan.revision)
    assert executor.scheduler.eligible(session.id, document, "P2")
    next_phase = executor.start_phase(session, phase.plan, "P2")
    await executor.phase_tasks[next_phase.id]
    records = [r for r in executor.runs.list(session.id) if r.package_id.startswith("P2-")]
    assert records and records[0].base_commit == phase.staging_commit
    await executor.close()


async def test_reject_and_repair_preserve_history_and_make_new_attempt_ids(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    old_runs = executor.runs.list(session.id)
    rejected = await executor.review_phase(
        session.id, phase.plan, "P1", phase.review_hash, "reject", "Please repair"
    )
    assert rejected.status == "blocked"
    with pytest.raises(ValueError):
        await executor.reconcile_phase(session, phase.plan, "P1", phase.review_hash)
    document = executor.sessions.get_plan(session.id, phase.plan.plan_id, phase.plan.revision)
    with pytest.raises(ValueError):
        executor.scheduler.eligible(session.id, document, "P2")
    repaired = executor.repair_phase(session, phase.plan, "P1", phase.review_hash)
    await executor.phase_tasks[repaired.id]
    current = executor.runs.phase(session.id, phase.plan.content_hash, "P1")
    assert current.attempt == 2 and current.status == "awaiting_phase_review", current.error
    assert current.review_hash != phase.review_hash
    assert len(executor.runs.list(session.id)) == 4
    assert all(Path(r.worktree).is_dir() for r in old_runs)
    assert executor.runs.review(phase.review_hash)
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    await executor.close()


async def test_failed_required_check_and_stale_requirements_never_accept(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    run = executor.runs.list(session.id)[0]
    executor.runs.patch(run.id, lambda r: r.evidence["checks"][0].update(exit_code=1))
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    session.revision += 1
    executor.sessions.save(session)
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    await executor.close()


async def test_review_api_requires_exact_identity_and_exposes_immutable_review(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        base = f"/api/sessions/{session.id}/execution"
        detail = (await client.get(base)).json()
        assert detail["phase_acceptance_enabled"]
        assert detail["session_id"] == session.id
        assert detail["reviews"][0]["evidence_hash"] == phase.review_hash
        artifact = base + f"/phases/P1/artifacts/contracts/result.txt?evidence_hash={phase.review_hash}"
        download = await client.get(artifact)
        assert download.status_code == 200
        assert download.content == b"Synthetic artifact"
        assert "attachment" in download.headers["content-disposition"]
        assert (
            await client.get(base + "/phases/P1/artifacts/outside.txt?evidence_hash=" + phase.review_hash)
        ).status_code == 404
        request = {**phase.plan.model_dump(), "decision": "accept", "evidence_hash": "a" * 64}
        assert (await client.post(base + "/phases/P1/review", json=request)).status_code == 409
        request["evidence_hash"] = phase.review_hash
        response = await client.post(base + "/phases/P1/review", json=request)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"
    await executor.close()


async def test_unknown_promotion_is_not_replayed_and_can_be_explicitly_reconciled(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    git = executor.worktrees.git

    async def lost_reply(cwd, *args, **kwargs):
        result = await git(cwd, *args, **kwargs)
        if args[:2] == ("update-ref", "refs/heads/accepted"):
            raise ValueError("Synthetic lost promotion reply")
        return result

    executor.worktrees.git = lost_reply
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    state = executor.runs.phase(session.id, phase.plan.content_hash, "P1")
    assert state.status == "blocked" and state.promotion_intent == phase.review_hash
    with pytest.raises(ValueError):
        executor.repair_phase(session, phase.plan, "P1", phase.review_hash)
    executor.worktrees.git = git
    await executor.recover()
    assert executor.runs.phase(session.id, phase.plan.content_hash, "P1").status == "blocked"
    result = await executor.reconcile_phase(session, phase.plan, "P1", phase.review_hash)
    assert result.status == "accepted" and result.promotion_intent is None
    await executor.close()


async def test_moved_accepted_ref_rejects_promotion_and_preserves_evidence(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    project = await executor.worktrees.owned_project(session.id)
    tree = (await executor.worktrees.git(project, "rev-parse", phase.base_commit + "^{tree}")).strip()
    other = (
        await executor.worktrees.git(
            project, "commit-tree", tree, "-p", phase.base_commit, "-m", "Synthetic external change"
        )
    ).strip()
    await executor.worktrees.git(project, "update-ref", "refs/heads/accepted", other, phase.base_commit)
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    assert executor.runs.phase(session.id, phase.plan.content_hash, "P1").status != "accepted"
    assert executor.runs.review(phase.review_hash)
    await executor.close()


async def test_phase_cancel_preserves_staging_and_stops_future_dispatch(tmp_path):
    session, _, executor, phase = await ready(tmp_path)
    cancelled = await executor.cancel_phase(session.id, phase.plan, "P1")
    assert cancelled.status == "cancelled"
    assert cancelled.staging_commit == phase.staging_commit
    with pytest.raises(ValueError):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    await executor.close()


async def test_successor_completes_from_accepted_tree_without_rerunning_prior_packages(tmp_path):
    session, _, executor = scoped_fixture(tmp_path, "scoped_artifact", successor=True)
    first = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[first.id]
    first = executor.runs.phase(session.id, first.plan.content_hash, "P1")
    await executor.review_phase(session.id, first.plan, "P1", first.review_hash, "accept")
    second = executor.start_phase(session, first.plan, "P2")
    await executor.phase_tasks[second.id]
    second = executor.runs.phase(session.id, first.plan.content_hash, "P2")
    assert second.status == "awaiting_phase_review", second.error
    assert second.base_commit == first.staging_commit
    accepted = await executor.review_phase(session.id, second.plan, "P2", second.review_hash, "accept")
    assert accepted.status == "accepted"
    assert len(executor.runs.list(session.id)) == 3
    await executor.close()


async def test_successor_never_starts_from_an_unreviewed_accepted_ref_movement(tmp_path):
    session, _, executor, first = await ready(tmp_path)
    await executor.review_phase(session.id, first.plan, "P1", first.review_hash, "accept")
    project = await executor.worktrees.owned_project(session.id)
    tree = (await executor.worktrees.git(project, "rev-parse", first.staging_commit + "^{tree}")).strip()
    other = (
        await executor.worktrees.git(
            project, "commit-tree", tree, "-p", first.staging_commit, "-m", "Synthetic external movement"
        )
    ).strip()
    await executor.worktrees.git(project, "update-ref", "refs/heads/accepted", other, first.staging_commit)
    second = executor.start_phase(session, first.plan, "P2")
    await executor.phase_tasks[second.id]
    run = next(r for r in executor.runs.list(session.id) if r.package_id == "P2-W1")
    assert run.base_commit == first.staging_commit
    assert run.status == "blocked"
    await executor.close()
