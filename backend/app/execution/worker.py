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
from .contracts import Run
from .scheduler import Scheduler
from .store import ExecutionStore
from .worktrees import Worktrees


class Executor:
    def __init__(self, settings, sessions, factory=None):
        self.settings, self.sessions = settings, sessions
        self.runs = ExecutionStore(sessions)
        self.scheduler = Scheduler(
            self.runs, capacity=settings.codex_max_workers, global_capacity=settings.codex_global_max_workers
        )
        self.worktrees = Worktrees(settings.codex_project_root, settings.codex_worktree_root)
        self.factory = factory or self.default_client
        self.profile = str(
            Path(settings.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
        )
        self.tasks, self.clients = {}, {}
        self.locks = defaultdict(asyncio.Lock)

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
        document = self.guard(session, identity)
        package = next(
            (p for p in self.scheduler.eligible(session.id, document, "P1") if p.id == package_id), None
        )
        if package is None:
            raise ValueError("Package is attempted, dependent, or in an ineligible phase")
        for path in package.owned_paths:
            if path.split("/")[0].casefold() in {".git", "agents.md", "claude.md"}:
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
        self.scheduler.claim(
            run, package.owned_paths, [i.name for i in [*package.produces, *package.consumes]]
        )
        # Durable ownership precedes every filesystem/process side effect.
        self.tasks[run.id] = asyncio.create_task(self.execute(run.id))
        return run

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
                    text = str(event["params"].get("delta", ""))[:2000]

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
            except (CodexError, TimeoutError):
                pass
        task = self.tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.stop_peers(run_id)
        return self.runs.get(run_id)

    async def invalidate(self, session_id):
        for run in self.runs.list(session_id):
            if run.status in {"queued", "running", "verifying", "blocked"} and not run.stale:
                await self.cancel(session_id, run.id, stale=True)

    async def reconcile(self, session_id, run_id, *, wait=True):
        run = self.owned(session_id, run_id)
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

    async def close(self):
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
