import hashlib

import httpx
import pytest

from backend.app.main import create_app
from backend.app.planning.contracts import Check, PlanApproval
from backend.tests.test_codex_worker import fixture


def context_fixture(tmp_path, scenario="artifact"):
    session, document, executor = fixture(tmp_path, scenario)
    document.id = "context-review"
    package = document.phases[0].packages[0]
    package.artifacts = ["contracts/result.txt"]
    package.tasks[0].checks = [Check(command=["git", "diff", "--check"], expected="No whitespace errors")]
    identity = PlanApproval(
        plan_id=document.id,
        revision=document.revision,
        content_hash=document.content_hash,
        requirements_revision=document.requirements_revision,
    )
    session.planning.active = session.planning.approval = identity
    executor.sessions.save(session)
    executor.sessions.save_plan(session.id, document)
    return session, document, executor


async def approve(session, executor, package_id="P1-W1"):
    record = await executor.prepare_context(session, session.planning.approval, package_id)
    return await executor.approve_context(
        session, session.planning.approval, record.context_hash, record.packet.packet_hash
    )


async def test_prepare_and_approval_do_not_start_a_worker_and_are_idempotent(tmp_path):
    session, document, executor = context_fixture(tmp_path)
    first = await executor.prepare_context(session, session.planning.approval, "P1-W1")
    second = await executor.prepare_context(session, session.planning.approval, "P1-W1")
    assert first == second and not first.approved
    assert not executor.runs.list(session.id) and not executor.clients
    with pytest.raises(ValueError, match="context|Context"):
        executor.start(session, session.planning.approval, "P1-W1")
    approved = await approve(session, executor)
    assert approved.approved
    assert approved == await approve(session, executor)
    assert not executor.runs.list(session.id)
    assert (
        executor.sessions.get_plan(session.id, document.id, document.revision).content_hash
        == document.content_hash
    )
    await executor.close()


async def test_exact_saved_packet_is_the_actual_turn_input_and_review_evidence(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    recorded = []
    factory = executor.factory

    async def capture(run):
        client = await factory(run)
        start = client.start_turn

        async def turn(thread, text, cwd):
            recorded.append(text)
            return await start(thread, text, cwd)

        client.start_turn = turn
        return client

    executor.factory = capture
    approved = await approve(session, executor)
    run = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[run.id]
    saved = executor.runs.get(run.id)
    assert recorded == [approved.packet.text]
    assert hashlib.sha256(recorded[0].encode()).hexdigest() == saved.packet_hash
    assert saved.context_hash == approved.context_hash
    assert "ROOT.json" in recorded[0] and "PHASE.json" in recorded[0] and "HANDOFF.json" in recorded[0]
    integrated = await executor.verify_run(session.id, run.id)
    assert integrated.status == "integrated", integrated.error
    assert integrated.evidence["context_hash"] == approved.context_hash
    await executor.close()


async def test_phase_pauses_until_explicit_context_approval_and_resume(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    phase = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[phase.id]
    assert executor.runs.phase(session.id, phase.plan.content_hash, "P1").status == "awaiting_context_review"
    assert not executor.runs.list(session.id)
    await approve(session, executor)
    assert not executor.runs.list(session.id)
    resumed = executor.resume_context_phase(session, phase.plan, "P1")
    await executor.phase_tasks[resumed.id]
    assert executor.runs.phase(session.id, phase.plan.content_hash, "P1").status == "awaiting_phase_review"
    await executor.close()


async def test_unsupported_checks_block_before_project_or_client_creation(tmp_path):
    session, document, executor = context_fixture(tmp_path)
    document.id = "unsupported-check"
    document.phases[0].packages[0].tasks[0].checks[0].command = ["echo", "TODO"]
    identity = session.planning.approval.model_copy(
        update={"plan_id": document.id, "content_hash": document.content_hash}
    )
    session.planning.active = session.planning.approval = identity
    executor.sessions.save(session)
    executor.sessions.save_plan(session.id, document)
    with pytest.raises(ValueError, match="check|command|trusted"):
        await executor.prepare_context(session, identity, "P1-W1")
    assert not (tmp_path / "projects" / session.id).exists()
    assert not executor.clients
    await executor.close()


async def test_tampered_saved_packet_and_legacy_run_cannot_resume(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    record = await approve(session, executor)
    run = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[run.id]
    executor.set(run.id, status="blocked", context_hash=None)
    with pytest.raises(ValueError, match="context|Context"):
        await executor.reconcile(session.id, run.id)
    executor.set(run.id, context_hash=record.context_hash)
    with executor.sessions.connect() as db:
        db.execute(
            "UPDATE execution_contexts SET state=replace(state, ?, ?) WHERE session_id=?",
            ("No whitespace errors", "FORGED INPUT", session.id),
        )
    with pytest.raises(ValueError, match="context|Context|packet|Packet"):
        await executor.reconcile(session.id, run.id)
    assert len(executor.runs.list(session.id)) == 1
    await executor.close()


async def test_context_api_separates_plan_approval_context_approval_and_dispatch(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        base = f"/api/sessions/{session.id}/execution"
        identity = session.planning.approval.model_dump()
        request = identity | {"package_id": "P1-W1"}
        assert (await client.post(base, json=request)).status_code == 409
        prepared = await client.post(base + "/contexts/prepare", json=request)
        assert prepared.status_code == 200, prepared.text
        record = prepared.json()
        assert not record["approved"] and record["text"]
        path = base + "/contexts/" + record["context_hash"]
        rejected = await client.post(path + "/approve", json=identity | {"packet_hash": "f" * 64})
        assert rejected.status_code == 409
        accepted = await client.post(
            path + "/approve", json=identity | {"packet_hash": record["packet_hash"]}
        )
        assert accepted.status_code == 200, accepted.text
        bundle = await client.get(path + "/bundle")
        assert bundle.status_code == 200 and bundle.content.startswith(b"PK")
        assert not app.state.executor.runs.list(session.id)
        response = await client.post(base, json=request)
        assert response.status_code == 200, response.text
        await app.state.executor.tasks[response.json()["id"]]
    await app.state.executor.close()


async def test_base_change_during_qualification_cannot_create_a_thread(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    await approve(session, executor)
    factory = executor.factory
    threads = []

    async def capture(run):
        client = await factory(run)
        qualify, start_thread = client.qualify, client.start_thread

        async def moved(*args):
            result = await qualify(*args)
            phase = executor.runs.phase(session.id, run.plan.content_hash, "P1")
            executor.runs.patch_phase(phase, lambda p: setattr(p, "staging_commit", "f" * 40))
            return result

        async def thread(*args):
            threads.append(args)
            return await start_thread(*args)

        client.qualify, client.start_thread = moved, thread
        return client

    executor.factory = capture
    run = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[run.id]
    assert threads == []
    assert executor.runs.get(run.id).status == "blocked"
    await executor.close()


async def test_accepted_ref_change_after_context_review_blocks_before_codex_process(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    record = await approve(session, executor)
    project = await executor.worktrees.owned_project(session.id)
    tree = (await executor.worktrees.git(project, "rev-parse", record.base_commit + "^{tree}")).strip()
    moved = (
        await executor.worktrees.git(
            project, "commit-tree", tree, "-p", record.base_commit, "-m", "External ref movement"
        )
    ).strip()
    await executor.worktrees.git(project, "update-ref", "refs/heads/accepted", moved, record.base_commit)
    calls = []

    async def forbidden(run):
        calls.append(run.id)
        raise AssertionError("A stale accepted ref cannot create a Codex process")

    executor.factory = forbidden
    run = executor.start(session, session.planning.approval, "P1-W1")
    await executor.tasks[run.id]
    assert calls == []
    assert executor.runs.get(run.id).status == "blocked"
    await executor.close()


async def test_phase_acceptance_rechecks_actual_run_context_identity(tmp_path):
    session, _, executor = context_fixture(tmp_path)
    await approve(session, executor)
    phase = executor.start_phase(session, session.planning.approval, "P1")
    await executor.phase_tasks[phase.id]
    phase = executor.runs.phase(session.id, phase.plan.content_hash, "P1")
    assert phase.status == "awaiting_phase_review", phase.error
    executor.set(executor.runs.list(session.id)[0].id, context_hash=None)
    with pytest.raises(ValueError, match="context|Context"):
        await executor.review_phase(session.id, phase.plan, "P1", phase.review_hash, "accept")
    await executor.close()


async def test_instruction_upgrade_preserves_readable_history_and_blocks_old_dispatch(tmp_path, monkeypatch):
    from backend.app.planning import context

    session, _, executor = context_fixture(tmp_path)
    original = await approve(session, executor)
    monkeypatch.setattr(
        context, "INSTRUCTIONS", context.INSTRUCTIONS + "\nNew reviewed instruction policy.\n"
    )
    historical = executor.contexts.get(session.id, original.context_hash)
    assert historical.packet.text == original.packet.text and historical.approved
    with pytest.raises(ValueError, match="context|Context|policy"):
        executor.start(session, session.planning.approval, "P1-W1")
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(f"/api/sessions/{session.id}/execution")
        assert response.status_code == 200
        record = response.json()["contexts"][0]
        assert record["text"] == original.packet.text and not record["current"]
    replacement = await approve(session, executor)
    assert replacement.context_hash != original.context_hash
    assert len(executor.contexts.list(session.id)) == 2
    await app.state.executor.close()
    await executor.close()
