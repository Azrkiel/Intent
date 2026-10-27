import asyncio
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path

from ..codex.client import Client
from ..codex.protocol import CodexError
from ..codex.transport import Transport
from ..domain import gate_for
from ..planning.export import COMMON_RULES
from ..planning.render import render_package
from ..planning.validation import safe_path, validate_plan
from .contracts import PhaseExecution, Run
from .review import PhaseReviews, transition
from .scheduler import Scheduler
from .store import ExecutionStore
from .verification import VerificationFailure, Verifier, protected, redact
from .worktrees import Worktrees


class Executor:
    def __init__(self, settings, sessions, factory=None):
        self.settings, self.sessions = settings, sessions
        self.runs = ExecutionStore(sessions)
        self.scheduler = Scheduler(
            self.runs, capacity=settings.codex_max_workers, global_capacity=settings.codex_global_max_workers
        )
        self.worktrees = Worktrees(settings.codex_project_root, settings.codex_worktree_root)
        self.verifier = Verifier(self.worktrees)
        self.factory = factory or self.default_client
        self.profile = str(
            Path(settings.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
        )
        self.tasks, self.clients = {}, {}
        self.phase_tasks = {}
        self.locks = defaultdict(asyncio.Lock)
        self.reviews = PhaseReviews(self)
        self.dispatch_ready = True

    async def default_client(self, run):
        executable = shutil.which(self.settings.codex_command)
        if not executable:
            raise CodexError("Codex executable is unavailable")
        transport = Transport([executable, "app-server"], cwd=run.worktree, home=self.profile)
        await transport.start()
        return Client(transport, self.settings.codex_approval_timeout_seconds)

    def guard(self, session, identity):
        if not self.settings.allow_codex_execution:
            raise ValueError("Set ALLOW_CODEX_EXECUTION=true explicitly before running Codex")
        if session.mode != "live" or self.settings.mode != "live":
            raise ValueError("Demo sessions and synthetic plans cannot invoke Codex")
        if (
            session.approved_revision != session.revision
            or not gate_for(session).ready
            or session.planning.status != "approved"
            or session.planning.active != identity
            or session.planning.approval != identity
            or identity.requirements_revision != session.revision
        ):
            raise ValueError("Execution requires the current approved plan hash and requirements revision")
        if session.build.status == "running":
            raise ValueError("Another coding adapter is running")
        document = self.sessions.get_plan(session.id, identity.plan_id, identity.revision)
        if document.mode != "live" or document.content_hash != identity.content_hash:
            raise ValueError("Plan identity is stale or synthetic")
        validate_plan(document, session.ledger)
        return document

    def start(self, session, identity, package_id, model=None):
        if not self.dispatch_ready:
            raise ValueError("Startup reconciliation is still running")
        document = self.guard(session, identity)
        package = next(
            (
                p
                for p in self.scheduler.eligible(session.id, document, package_id.split("-W")[0])
                if p.id == package_id
            ),
            None,
        )
        if package is None:
            raise ValueError("Package is attempted, dependent, or in an ineligible phase")
        for path in package.owned_paths:
            if protected(path):
                raise ValueError("Execution control files cannot be worker-owned paths")
        run = Run(
            session_id=session.id,
            plan=identity,
            package_id=package_id,
            model=model,
            profile=self.profile,
            deadline=time.time() + self.settings.codex_timeout_seconds,
        )
        run.project, run.worktree = map(str, self.worktrees.paths(session.id, run.id))
        try:
            phase = self.runs.phase(session.id, identity.content_hash, package_id.split("-W")[0])
            if phase.status != "running" or phase.integration_intent:
                raise ValueError("Phase is blocked, already reviewing, or has uncertain integration")
            run.base_commit = phase.staging_commit
            run.phase_attempt = phase.attempt
        except KeyError:
            phase = self.runs.ensure_phase(
                self.new_phase(session.id, identity, document, package_id.split("-W")[0])
            )
            run.base_commit, run.phase_attempt = phase.staging_commit, phase.attempt
        self.scheduler.claim(
            run,
            package.owned_paths,
            [f"write:{i.name}@{i.version}" for i in package.produces]
            + [f"read:{i.name}@{i.version}" for i in package.consumes],
        )
        # Durable ownership precedes every filesystem/process side effect.
        self.tasks[run.id] = asyncio.create_task(self.execute(run.id))
        return run

    def start_phase(self, session, identity, phase_id, model=None):
        if not self.dispatch_ready:
            raise ValueError("Startup reconciliation is still running")
        document = self.guard(session, identity)
        eligible = self.scheduler.eligible(session.id, document, phase_id)
        existing = [p for p in self.runs.phases(session.id) if p.plan == identity and p.phase_id == phase_id]
        if existing or not eligible:
            raise ValueError("Phase already attempted or has no eligible packages; reconcile before resuming")
        phase = self.runs.ensure_phase(self.new_phase(session.id, identity, document, phase_id))
        if phase.id in self.phase_tasks:
            raise ValueError("Phase is already running")
        self.phase_tasks[phase.id] = asyncio.create_task(self.drive_phase(phase, model))
        return phase

    def new_phase(self, session_id, identity, document, phase_id):
        index = next(i for i, phase in enumerate(document.phases) if phase.id == phase_id)
        base = None
        if index:
            prior = self.runs.phase(session_id, identity.content_hash, document.phases[index - 1].id)
            if prior.status != "accepted" or prior.stale or not prior.staging_commit:
                raise ValueError("Earlier phase lacks a current accepted commit")
            base = prior.staging_commit
        return PhaseExecution(
            session_id=session_id, plan=identity, phase_id=phase_id, base_commit=base, staging_commit=base
        )

    async def drive_phase(self, phase, model):
        try:
            while True:
                document = self.guard(self.sessions.get(phase.session_id), phase.plan)
                current = self.runs.phase(phase.session_id, phase.plan.content_hash, phase.phase_id)
                if current.status != "running" or current.integration_intent:
                    raise ValueError("Phase is blocked or requires reconciliation")
                records = self.phase_runs(current)
                if any(r.status in {"blocked", "cancelled"} for r in records):
                    raise ValueError("Phase worker failed; review and repair are required")
                for run in records:
                    if run.status == "verifying" and (
                        not self.tasks.get(run.id) or self.tasks[run.id].done()
                    ):
                        await self.verify_run(phase.session_id, run.id)
                records = self.phase_runs(current)
                packages = next(p.packages for p in document.phases if p.id == phase.phase_id)
                if len([r for r in records if r.status == "integrated"]) == len(packages):

                    def ready(p):
                        if p.status != "running" or p.integration_intent:
                            raise ValueError("Phase changed during verification")
                        p.status = transition("phase", p.status, "verifying")

                    current = self.runs.patch_phase(phase, ready)
                    self.reviews.publish(current, document)
                    return
                active = [r for r in records if r.status in {"queued", "running", "verifying"}]
                available = min(self.scheduler.capacity, self.scheduler.global_capacity) - len(active)
                for package in self.scheduler.eligible(phase.session_id, document, phase.phase_id)[
                    :available
                ]:
                    self.start(self.sessions.get(phase.session_id), phase.plan, package.id, model)
                pending = [
                    task
                    for id, task in self.tasks.items()
                    if not task.done() and self.runs.get(id).session_id == phase.session_id
                ]
                if not pending:
                    if any(
                        r.status == "verifying" and self.tasks.get(r.id) and self.tasks[r.id].done()
                        for r in self.runs.list(phase.session_id)
                        if r.plan == phase.plan
                    ):
                        continue
                    raise ValueError("No dispatchable packages; phase requires review")
                await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            self.block_phase(phase, "Phase interrupted; preserve staging and reconcile before continuing")
            await self.stop_phase_workers(phase)
            raise
        except Exception:
            self.block_phase(phase, "Phase blocked; inspect package evidence and retained worktrees")
            await self.stop_phase_workers(phase)

    async def stop_phase_workers(self, phase):
        for run in self.runs.list(phase.session_id):
            if run.plan == phase.plan and run.status in {"queued", "running", "verifying"}:
                await self.cancel(phase.session_id, run.id)
                self.set(run.id, status="blocked", error="Phase controller stopped; preserve work for review")

    def block_phase(self, phase, message):
        def block(p):
            if p.status == "accepted":
                return
            p.status, p.error = "blocked", message

        return self.runs.patch_phase(phase, block)

    async def verify_run(self, session_id, run_id):
        run = self.owned(session_id, run_id)
        phase_id = run.package_id.split("-W")[0]
        async with self.locks["phase:" + session_id + run.plan.content_hash + phase_id]:
            run = self.check(run_id)
            if run.status == "integrated":
                return run
            if run.status != "verifying" or (run_id in self.tasks and not self.tasks[run_id].done()):
                raise ValueError("Only a completed worker awaiting verification can be inspected")
            phase = self.runs.ensure_phase(
                PhaseExecution(session_id=session_id, plan=run.plan, phase_id=phase_id)
            )
            try:
                document = self.guard(self.sessions.get(session_id), run.plan)
                package = next(p for ph in document.phases for p in ph.packages if p.id == run.package_id)
                evidence = await self.verifier.inspect(run, package)
                self.set(run_id, evidence=evidence.model_dump(), changed_paths=evidence.changed_paths)
                self.check(run_id)

                def reserve(p):
                    if p.status != "running" or p.integration_intent:
                        raise ValueError("Phase integration is blocked or uncertain")
                    if p.base_commit is None:
                        p.base_commit = p.staging_commit = run.base_commit
                    p.integration_intent = run_id

                phase = self.runs.patch_phase(phase, reserve)
                project = await self.worktrees.owned_project(session_id)
                accepted = (await self.worktrees.git(project, "rev-parse", "refs/heads/accepted")).strip()
                if accepted != phase.base_commit:
                    raise ValueError("Accepted project base changed; preserve worker and staging changes")
                commit = await self.verifier.integrate(run, evidence, phase.staging_commit)
                # Validate the aggregate in a new retained staging checkout before publishing the staging ref.
                stage_id = "stage-" + run.id
                await self.worktrees.create(session_id, stage_id, base_commit=commit)
                _, stage_path = self.worktrees.paths(session_id, stage_id)
                included = {r.package_id for r in self.phase_runs(phase) if r.status == "integrated"} | {
                    run.package_id
                }
                aggregate = package.model_copy(deep=True)
                done = [p for ph in document.phases for p in ph.packages if p.id in included]
                aggregate.owned_paths = [path for p in done for path in p.owned_paths]
                aggregate.artifacts = sorted({a for p in done for a in p.artifacts})
                aggregate.tasks = [t for p in done for t in p.tasks]
                aggregate.choices = [s for p in done for s in p.choices]
                stage_run = run.model_copy(
                    update={"id": stage_id, "worktree": str(stage_path), "base_commit": phase.base_commit}
                )
                aggregate_evidence = await self.verifier.inspect(stage_run, aggregate)
                self.check(run_id)
                current = self.runs.phase(session_id, run.plan.content_hash, phase_id)
                if current.integration_intent != run_id or current.status != "running":
                    raise ValueError("Phase changed before staging integration")
                # CAS protects against unknown ref movement. Never touch the accepted project branch.
                prior = phase.staging_commit if phase.staging_worktree else "0" * 40
                await self.worktrees.git(project, "update-ref", phase.branch, commit, prior)
                self.check(run_id)

                def finish(p):
                    if p.integration_intent != run_id or p.status != "running":
                        raise ValueError("Phase changed during staging integration")
                    p.staging_commit, p.staging_worktree = commit, str(stage_path)
                    p.evidence = aggregate_evidence.model_dump() | {
                        "package_attempt_ids": sorted(
                            r.id for r in self.phase_runs(phase) if r.package_id in included
                        )
                    }
                    p.integration_intent = None

                self.runs.patch_phase(phase, finish)
                return self.set(run_id, status="integrated", integrated_commit=commit)
            except asyncio.CancelledError:
                self.block_phase(
                    phase, "Verification interrupted; reconcile retained staging before retrying"
                )
                self.set(run_id, status="blocked", error="Verification interrupted; preserve work for review")
                await self.stop_peers(run_id)
                raise
            except Exception as error:
                current_run = self.runs.get(run_id)
                if current_run.cancel_requested:
                    self.block_phase(phase, "Verification interrupted by cancellation or plan change")
                    return current_run
                fields = {
                    "status": "blocked",
                    "error": str(error)[:500]
                    if isinstance(error, ValueError)
                    else "Package verification or integration failed",
                }
                if isinstance(error, VerificationFailure) and error.evidence:
                    fields["evidence"] = error.evidence.model_dump()
                    fields["changed_paths"] = error.evidence.changed_paths
                self.set(run_id, **fields)
                self.block_phase(phase, "Package verification/integration failed; preserve work for review")
                await self.stop_peers(run_id)
                return self.runs.get(run_id)

    def check(self, run_id):
        run = self.runs.get(run_id)
        if run.cancel_requested or run.stale or run.deadline <= time.time():
            raise CodexError("Run cancelled, stale, or past its deadline; preserve its work")
        if run.profile != self.profile:
            raise CodexError("Codex profile differs from the saved run")
        self.guard(self.sessions.get(run.session_id), run.plan)
        return run

    def set(self, run_id, **fields):
        def update(run):
            for name, value in fields.items():
                setattr(run, name, value)

        return self.runs.patch(run_id, update)

    async def execute(self, run_id, reconnect=False):
        client = None
        try:
            run = self.check(run_id)
            document = self.guard(self.sessions.get(run.session_id), run.plan)
            package = next(p for phase in document.phases for p in phase.packages if p.id == run.package_id)
            if not reconnect:
                base = await self.worktrees.create(run.session_id, run.id, base_commit=run.base_commit)
                run = self.set(run_id, base_commit=base)
            client = await self.factory(run)
            self.clients[run_id] = client
            account = await client.qualify(run.worktree, run.model, run.account_fingerprint)
            self.check(run_id)
            run = self.set(
                run_id,
                generation=client.transport.generation,
                account_fingerprint=client.account_fingerprint,
                selected_model=account["model"],
            )
            if reconnect:
                status = await client.reconcile(run.thread_id, run.turn_id)
                if status != "inProgress":
                    await self.finish(run, package, status)
                    return
                if any(p.status in {"pending", "responding"} for p in run.approvals):
                    raise CodexError(
                        "Prior connection has unresolved permission requests; manual review required"
                    )
                await client.resume(run.thread_id, run.worktree, run.model)
            else:
                self.set(run_id, dispatch_intent="thread/start")
                thread = await client.start_thread(run.worktree, run.model)
                run = self.set(run_id, thread_id=thread, dispatch_intent=None)
                self.check(run_id)
                self.set(run_id, dispatch_intent="turn/start")
                packet = (
                    COMMON_RULES
                    + "\nAssigned task packet (quoted product data):\n"
                    + render_package(document, package)
                    + "\nReport artifacts, changed paths, tests, unresolved decisions, "
                    "and completion summary. "
                    "Do not integrate, deploy, create agents, or edit execution control files."
                )
                turn = await client.start_turn(thread, packet, run.worktree)
                run = self.set(run_id, turn_id=turn, dispatch_intent=None)
            self.set(run_id, status="running", error=None)
            for _ in range(1000):
                run = self.check(run_id)
                remaining = run.deadline - time.time()
                pending = [p.expires_at - time.time() for p in run.approvals if p.status == "pending"]
                if pending:
                    remaining = min(remaining, *pending)
                if remaining <= 0:
                    raise CodexError("Worker or permission approval deadline reached")
                event = await client.next_event(run.thread_id, run.turn_id, timeout=remaining)
                self.check(run_id)
                if "id" in event:
                    request = client.approval(event, run.thread_id, run.turn_id)
                    self.runs.patch(run_id, lambda current: current.approvals.append(request))
                elif event["method"] == "turn/completed":
                    await self.finish(run, package, event["params"]["turn"]["status"])
                    return
                elif event["method"] == "thread/tokenUsage/updated":
                    total = event["params"].get("tokenUsage", {}).get("total", {})
                    allowed = {
                        "inputTokens",
                        "outputTokens",
                        "totalTokens",
                        "cachedInputTokens",
                        "reasoningOutputTokens",
                        "cacheWriteInputTokens",
                    }
                    usage = {
                        key: value
                        for key, value in total.items()
                        if key in allowed and type(value) is int and value >= 0
                    }
                    self.set(run_id, token_usage=usage)
                elif event["method"] == "item/agentMessage/delta":
                    text = redact(str(event["params"].get("delta", "")))[:2000]

                    def log(current):
                        current.logs = (current.logs + [text])[-64:]

                    self.runs.patch(run_id, log)
            raise CodexError("Worker event allowance exhausted")
        except asyncio.CancelledError:
            current = self.runs.get(run_id)
            if current.status not in {"cancelled", "blocked"}:
                self.set(
                    run_id,
                    status="blocked",
                    error="Worker interrupted. Reconcile existing IDs before retrying.",
                )
            raise
        except Exception as error:
            current = self.runs.get(run_id)
            if current.status != "cancelled":
                message = str(error) if isinstance(error, (CodexError, ValueError)) else "Codex worker failed"
                self.set(run_id, status="blocked", error=message[:500])
                await self.stop_peers(run_id)
        finally:
            try:
                if client:
                    await client.close()
            finally:
                self.clients.pop(run_id, None)

    async def finish(self, run, package, status):
        async with self.locks[run.id]:
            self.check(run.id)
            changed = await self.worktrees.changed_paths(Path(run.worktree), run.base_commit)
            self.check(run.id)
            self.set(run.id, changed_paths=changed, turn_status=status)
            for path in changed:
                safe_path(path)
                if not any(
                    path.casefold() == p.casefold() or path.casefold().startswith(p.casefold() + "/")
                    for p in package.owned_paths
                ):
                    raise CodexError("Out-of-scope changes block verification and integration")
                self.worktrees.checked(Path(run.worktree) / path, Path(run.worktree))
            if status != "completed":
                raise CodexError("Codex turn failed or was interrupted; phase remains blocked")
            if any(p.status in {"pending", "responding"} for p in self.runs.get(run.id).approvals):
                raise CodexError("Turn completed with unresolved permissions")
            self.set(run.id, status="verifying", error=None)

    def owned(self, session_id, run_id):
        run = self.runs.get(run_id)
        if run.session_id != session_id:
            raise KeyError(run_id)
        return run

    async def stop_peers(self, run_id):
        failed = self.runs.get(run_id)
        for peer in self.runs.list(failed.session_id):
            if (
                peer.id == run_id
                or peer.plan != failed.plan
                or peer.package_id.split("-W")[0] != failed.package_id.split("-W")[0]
                or peer.status not in {"queued", "running", "verifying"}
            ):
                continue
            self.set(
                peer.id,
                status="blocked",
                cancel_requested=True,
                error="Another package failed or was cancelled; preserve work for phase review",
            )
            client = self.clients.get(peer.id)
            if client and peer.thread_id and peer.turn_id:
                try:
                    await asyncio.wait_for(client.interrupt(peer.thread_id, peer.turn_id), 2)
                except (CodexError, TimeoutError):
                    pass
            task = self.tasks.get(peer.id)
            if task and not task.done():
                task.cancel()

    async def decide(self, session_id, run_id, request_id, decision, generation):
        async with self.locks[run_id]:
            run = self.owned(session_id, run_id)
            self.check(run_id)
            client = self.clients.get(run_id)
            request = next((p for p in run.approvals if p.id == request_id), None)
            if (
                not client
                or not request
                or request.status != "pending"
                or run.generation != generation
                or request.expires_at <= time.time()
                or decision not in {"accept", "decline", "cancel"}
            ):
                raise ValueError("Permission request is stale, expired, unavailable, or already answered")

            def mark(current, status):
                next(p for p in current.approvals if p.id == request_id).status = status

            self.runs.patch(run_id, lambda current: mark(current, "responding"))
            try:
                await client.decide(client.pending[request_id], decision, generation=generation)
                self.runs.patch(run_id, lambda current: mark(current, decision))
            except CodexError as error:
                self.set(
                    run_id, status="blocked", error="Permission response outcome is uncertain; no replay"
                )
                raise ValueError(str(error)) from error

    async def cancel(self, session_id, run_id, *, stale=False):
        run = self.owned(session_id, run_id)
        if run.status == "integrated" and not stale:
            raise ValueError("Integrated work requires phase review or rejection")
        self.set(
            run_id,
            cancel_requested=True,
            stale=run.stale or stale,
            status="blocked" if stale else "cancelled",
            error="Plan changed" if stale else "User cancelled",
        )
        client = self.clients.get(run_id)
        if client and run.thread_id and run.turn_id:
            try:
                await asyncio.wait_for(client.interrupt(run.thread_id, run.turn_id), 2)
                self.set(run_id, turn_status="interrupted")
            except (CodexError, TimeoutError):
                pass
        task = self.tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.stop_peers(run_id)
        return self.runs.get(run_id)

    async def invalidate(self, session_id):
        for phase in self.runs.phases(session_id):

            def stale(p):
                p.stale = True
                p.error = "Plan changed; phase evidence is stale"
                if p.status != "accepted":
                    p.status = "blocked"

            self.runs.patch_phase(phase, stale)
        for run in self.runs.list(session_id):
            if run.status in {"queued", "running", "verifying", "blocked"} and not run.stale:
                await self.cancel(session_id, run.id, stale=True)

    async def reconcile(self, session_id, run_id, *, wait=True):
        run = self.owned(session_id, run_id)
        if run.cancel_requested and not run.stale:
            # A failed interruption must not resurrect a cancelled run. History inspection is read-only.
            self.guard(self.sessions.get(session_id), run.plan)
            if not run.thread_id or not run.turn_id or run.dispatch_intent:
                return run
            if run.profile != self.profile:
                raise ValueError("Codex profile differs from the saved run")
            client = await self.factory(run)
            try:
                await client.qualify(run.worktree, run.model, run.account_fingerprint)
                status = await client.reconcile(run.thread_id, run.turn_id)
                return self.set(run_id, turn_status=status)
            finally:
                await client.close()
        if not run.thread_id or not run.turn_id or run.dispatch_intent:
            self.set(
                run_id,
                status="blocked",
                error="External dispatch outcome is uncertain; no duplicate launched",
            )
            return self.runs.get(run_id)
        if run.status in {"verifying", "integrated", "cancelled"}:
            return run
        if run_id in self.tasks and not self.tasks[run_id].done():
            raise ValueError("Run is already connected")
        self.check(run_id)
        self.tasks[run_id] = asyncio.create_task(self.execute(run_id, reconnect=True))
        if wait:
            await self.tasks[run_id]
        return self.runs.get(run_id)

    def phase_runs(self, phase):
        return [
            r
            for r in self.runs.current_runs(phase.session_id)
            if r.plan == phase.plan
            and r.package_id.split("-W")[0] == phase.phase_id
            and r.phase_attempt == phase.attempt
        ]

    async def cancel_phase(self, session_id, identity, phase_id):
        phase = self.runs.phase(session_id, identity.content_hash, phase_id)
        if phase.plan != identity or phase.status == "accepted" or phase.promotion_intent:
            raise ValueError("Accepted or uncertain promotion requires reconciliation")
        self.runs.patch_phase(phase, lambda p: setattr(p, "status", "cancelled"))
        controller = self.phase_tasks.get(phase.id)
        if controller and not controller.done():
            controller.cancel()
            await asyncio.gather(controller, return_exceptions=True)
        for run in self.phase_runs(phase):
            if run.status in {"queued", "running", "verifying", "blocked"}:
                await self.cancel(session_id, run.id)
        return self.runs.patch_phase(phase, lambda p: setattr(p, "status", "cancelled"))

    async def reconcile_phase(self, session, identity, phase_id, evidence_hash):
        document = self.guard(session, identity)
        phase = self.runs.phase(session.id, identity.content_hash, phase_id)
        if (
            phase.plan != identity
            or phase.stale
            or phase.review_hash != evidence_hash
            or phase.integration_intent
            or phase.decision == "reject"
        ):
            raise ValueError("Phase identity is stale or integration outcome is uncertain")
        if phase.promotion_intent:
            from .review import make_review

            review = make_review(phase, self.runs.list(session.id), document)
            if review.evidence_hash != evidence_hash or review != self.runs.review(evidence_hash):
                raise ValueError("Promotion evidence differs from the saved review")
            project = await self.reviews.validate_tree(phase)
            accepted = (await self.worktrees.git(project, "rev-parse", "refs/heads/accepted")).strip()
            if accepted not in {phase.staging_commit, phase.base_commit}:
                raise ValueError("Accepted ref has an unknown value; preserve all work")

            def reconciled(p):
                if p.promotion_intent != evidence_hash or p.stale:
                    raise ValueError("Promotion changed during reconciliation")
                p.promotion_intent = None
                p.status = "accepted" if accepted == phase.staging_commit else "awaiting_phase_review"
                p.decision = "accept" if p.status == "accepted" else None
                p.error = None

            return self.runs.patch_phase(phase, reconciled)
        records = self.phase_runs(phase)
        if (
            phase.status != "blocked"
            or not records
            or any(
                r.status not in {"verifying", "integrated"} or r.stale or r.cancel_requested for r in records
            )
        ):
            raise ValueError("Reconcile existing worker outcomes before resuming phase verification")
        if phase.id in self.phase_tasks and not self.phase_tasks[phase.id].done():
            raise ValueError("Phase controller is still running")
        phase = self.runs.patch_phase(phase, lambda p: setattr(p, "status", "running"))
        self.phase_tasks[phase.id] = asyncio.create_task(self.drive_phase(phase, None))
        return phase

    async def review_phase(self, session_id, identity, phase_id, evidence_hash, decision, notes=""):
        return await self.reviews.decide(session_id, identity, phase_id, evidence_hash, decision, notes)

    def repair_phase(self, session, identity, phase_id, evidence_hash, model=None, expected_attempt=1):
        if not self.dispatch_ready:
            raise ValueError("Startup reconciliation is still running")
        document = self.guard(session, identity)
        phase = self.runs.phase(session.id, identity.content_hash, phase_id)
        records = self.phase_runs(phase)
        if any(
            (r.id in self.tasks and not self.tasks[r.id].done())
            or r.dispatch_intent
            or (r.thread_id and r.turn_status not in {"completed", "failed", "interrupted"})
            for r in records
        ):
            raise ValueError("Reconcile or interrupt existing worker outcomes before repair")
        if phase.id in self.phase_tasks and not self.phase_tasks[phase.id].done():
            raise ValueError("Phase controller is still running")
        # Recheck predecessor acceptance before releasing any old claims.
        for earlier in document.phases[: next(i for i, p in enumerate(document.phases) if p.id == phase_id)]:
            prior = self.runs.phase(session.id, identity.content_hash, earlier.id)
            if prior.status != "accepted" or prior.stale:
                raise ValueError("Earlier phases must be accepted")
        phase = self.runs.repair(phase, expected_attempt, evidence_hash)
        self.phase_tasks[phase.id] = asyncio.create_task(self.drive_phase(phase, model))
        return phase

    async def recover(self):
        """Inspect history before enabling dispatch. Never start/resume turns at startup."""
        self.dispatch_ready = False
        self.runs.recover()
        try:
            for summary in self.sessions.list():
                for run in self.runs.current_runs(summary["id"]):
                    if run.status in {"integrated", "cancelled"} or run.stale or run.cancel_requested:
                        continue
                    if not run.thread_id or not run.turn_id or run.dispatch_intent:
                        self.set(run.id, status="blocked", error="Unknown dispatch outcome; no replay")
                        continue
                    client = None
                    try:
                        self.guard(self.sessions.get(run.session_id), run.plan)
                        client = await self.factory(run)
                        await client.qualify(run.worktree, run.model, run.account_fingerprint)
                        status = await client.reconcile(run.thread_id, run.turn_id)
                        self.set(run.id, turn_status=status)
                        if status == "completed" and not any(
                            p.status in {"pending", "responding"} for p in run.approvals
                        ):
                            document = self.guard(self.sessions.get(run.session_id), run.plan)
                            package = next(
                                p for ph in document.phases for p in ph.packages if p.id == run.package_id
                            )
                            await self.finish(run, package, status)
                        else:
                            self.set(
                                run.id,
                                status="blocked",
                                error="Saved turn requires explicit reconciliation or repair",
                            )
                    except Exception:
                        self.set(
                            run.id,
                            status="blocked",
                            error="Saved thread could not be reconciled; no replacement dispatched",
                        )
                    finally:
                        if client:
                            await client.close()
                for phase in self.runs.phases(summary["id"]):
                    if phase.status == "awaiting_phase_review" and not phase.review_hash:
                        try:
                            document = self.guard(self.sessions.get(phase.session_id), phase.plan)
                            await self.reviews.validate_tree(phase)
                            self.reviews.publish(phase, document)
                        except Exception:
                            self.block_phase(phase, "Prior phase evidence requires review and repair")
        finally:
            self.dispatch_ready = True

    async def close(self):
        for task in self.phase_tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.phase_tasks.values(), return_exceptions=True)
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
