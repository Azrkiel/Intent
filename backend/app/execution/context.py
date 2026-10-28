"""Durable context reviews. Preparing or approving a packet never dispatches it."""

import hashlib

from pydantic import BaseModel, ConfigDict, Field

from ..domain import Session
from ..planning.context import (
    SharedContractSnapshot,
    WorkerPacket,
    build_context,
    preflight_checks,
    verify_packet,
)
from ..planning.contracts import PlanApproval, content_hash
from ..planning.validation import safe_path
from .contracts import PhaseExecution
from .review import required_evidence
from .verification import protected


class ContextReviewRequired(ValueError):
    pass


class ContextRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    plan: PlanApproval
    package_id: str
    phase_attempt: int
    base_commit: str
    packet: WorkerPacket
    snapshots: list[SharedContractSnapshot] = Field(default_factory=list)
    approved: bool = False

    @property
    def context_hash(self):
        return self.packet.context_hash

    @property
    def review_hash(self):
        return content_hash(
            {
                "session_id": self.session_id,
                "plan": self.plan.model_dump(),
                "package_id": self.package_id,
                "phase_attempt": self.phase_attempt,
                "base_commit": self.base_commit,
                "context_hash": self.context_hash,
                "packet_hash": self.packet.packet_hash,
                "manifest_hash": self.packet.manifest_hash,
                "snapshots": [s.model_dump(mode="json") for s in self.snapshots],
                "verification_policy": self.packet.payload["verification_policy"],
            }
        )

    def public(self):
        return {
            **self.model_dump(mode="json", exclude={"packet", "snapshots"}),
            "context_hash": self.context_hash,
            "packet_hash": self.packet.packet_hash,
            "manifest_hash": self.packet.manifest_hash,
            "review_hash": self.review_hash,
            "text": self.packet.text,
            "documents": self.packet.documents,
            "snapshots": [s.model_dump(mode="json", exclude={"documents"}) for s in self.snapshots],
        }


class ExecutionContexts:
    def __init__(self, sessions):
        self.sessions = sessions
        with sessions.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS execution_contexts (session_id TEXT NOT NULL, "
                "hash TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(session_id,hash))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS execution_context_approvals (session_id TEXT NOT NULL, "
                "hash TEXT NOT NULL, review_hash TEXT NOT NULL, packet_hash TEXT NOT NULL, "
                "PRIMARY KEY(session_id,hash))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS shared_contract_snapshots (session_id TEXT NOT NULL, "
                "hash TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(session_id,hash))"
            )

    @staticmethod
    def load(db, session_id, digest):
        row = db.execute(
            "SELECT state FROM execution_contexts WHERE session_id=? AND hash=?", (session_id, digest)
        ).fetchone()
        if row is None:
            raise ContextReviewRequired("Execution context is missing; prepare and review exact inputs")
        record = ContextRecord.model_validate_json(row[0])
        verify_packet(record.packet, current_policy=False)
        if record.session_id != session_id or record.context_hash != digest:
            raise ValueError("Execution context identity differs from its saved key")
        approval = db.execute(
            "SELECT review_hash,packet_hash FROM execution_context_approvals WHERE session_id=? AND hash=?",
            (session_id, digest),
        ).fetchone()
        if approval and approval != (record.review_hash, record.packet.packet_hash):
            raise ValueError("Execution context approval differs from its immutable packet")
        record.approved = approval is not None
        return record

    def get(self, session_id, digest):
        with self.sessions.connect() as db:
            return self.load(db, session_id, digest)

    def list(self, session_id):
        with self.sessions.connect() as db:
            hashes = db.execute(
                "SELECT hash FROM execution_contexts WHERE session_id=? ORDER BY rowid DESC", (session_id,)
            ).fetchall()
            return [self.load(db, session_id, row[0]) for row in hashes]

    def save(self, record):
        verify_packet(record.packet)
        state = record.model_dump_json(exclude={"approved"})
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT state FROM execution_contexts WHERE session_id=? AND hash=?",
                (record.session_id, record.context_hash),
            ).fetchone()
            if prior and prior[0] != state:
                raise ValueError("Immutable execution context collision")
            db.execute(
                "INSERT OR IGNORE INTO execution_contexts VALUES(?,?,?)",
                (record.session_id, record.context_hash, state),
            )
            for snapshot in record.snapshots:
                value = snapshot.model_dump(mode="json")
                db.execute(
                    "INSERT OR IGNORE INTO shared_contract_snapshots VALUES(?,?,?)",
                    (record.session_id, content_hash(value), snapshot.model_dump_json()),
                )
        return self.get(record.session_id, record.context_hash)

    @staticmethod
    def source_guard(db, record):
        row = db.execute("SELECT state FROM sessions WHERE id=?", (record.session_id,)).fetchone()
        if not row:
            raise ValueError("Context session no longer exists")
        session = Session.model_validate_json(row[0])
        if (
            session.planning.approval != record.plan
            or session.planning.active != record.plan
            or session.planning.status != "approved"
            or session.revision != record.plan.requirements_revision
            or session.approved_revision != session.revision
        ):
            raise ValueError("Execution context source approval is stale")
        row = db.execute(
            "SELECT state FROM execution_phases WHERE session_id=? AND plan_hash=? AND phase_id=?",
            (record.session_id, record.plan.content_hash, record.package_id.split("-W")[0]),
        ).fetchone()
        if row:
            phase = PhaseExecution.model_validate_json(row[0])
            if (
                phase.stale
                or phase.attempt != record.phase_attempt
                or phase.integration_intent
                or phase.promotion_intent
                or phase.status not in {"running", "awaiting_context_review"}
                or phase.staging_commit not in {None, record.base_commit}
            ):
                raise ValueError("Execution context phase attempt or input base is stale")

    def approve(self, record, packet_hash):
        if record.packet.packet_hash != packet_hash:
            raise ValueError("Review the exact packet hash before context approval")
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            saved = self.load(db, record.session_id, record.context_hash)
            self.source_guard(db, saved)
            if saved.review_hash != record.review_hash:
                raise ValueError("Context changed during approval")
            db.execute(
                "INSERT OR IGNORE INTO execution_context_approvals VALUES(?,?,?,?)",
                (record.session_id, record.context_hash, record.review_hash, packet_hash),
            )
        return self.get(record.session_id, record.context_hash)

    def approved_for(self, session_id, identity, package_id, base_commit, phase_attempt):
        for record in self.list(session_id):
            if (
                record.approved
                and record.plan == identity
                and record.package_id == package_id
                and record.phase_attempt == phase_attempt
                and record.base_commit == base_commit
            ):
                return record
        raise ContextReviewRequired("Execution context review is required for this package and input base")

    def validate_claim(self, db, run):
        if not run.context_hash:
            raise ContextReviewRequired("Execution context review is required before dispatch")
        record = self.load(db, run.session_id, run.context_hash)
        self.source_guard(db, record)
        if (
            not record.approved
            or record.plan != run.plan
            or record.package_id != run.package_id
            or record.phase_attempt != run.phase_attempt
            or record.base_commit != run.base_commit
            or record.packet.packet_hash != run.packet_hash
            or record.review_hash != run.context_review_hash
        ):
            raise ValueError("Run identity differs from the approved execution context")


async def published_snapshots(executor, session, document, package, selections):
    """Resolve explicitly selected published inputs from trusted integrated Git bytes."""
    packages = {p.id: p for phase in document.phases for p in phase.packages}
    runs = {
        r.package_id: r for r in executor.runs.current_runs(session.id) if r.plan == session.planning.approval
    }
    dependency_ids = document.dependency_ids[package.id]
    result, total = [], 0
    for selection in selections:
        producer_id = selection["producer_id"]
        if producer_id not in dependency_ids:
            raise ValueError("Publication producer must be a direct package dependency")
        producer = packages[producer_id]
        run = runs.get(producer_id)
        if (
            not run
            or run.status != "integrated"
            or run.stale
            or run.cancel_requested
            or not run.integrated_commit
        ):
            raise ValueError("Shared input producer has no current trusted integration")
        executor.check_context(run)
        required_evidence(run.evidence, [producer])
        paths = selection["paths"]
        if not paths or len(paths) != len(set(p.casefold() for p in paths)):
            raise ValueError("Explicit nonempty unique shared artifact selection is required")
        interface = selection.get("interface_name"), selection.get("interface_version")
        if interface != (None, None) and not any((i.name, i.version) == interface for i in producer.produces):
            raise ValueError("Publication interface differs from the producer declaration")
        phase = executor.runs.phase(session.id, run.plan.content_hash, producer_id.split("-W")[0])
        same_phase = producer_id.split("-W")[0] == package.id.split("-W")[0]
        if (
            phase.stale
            or phase.attempt != run.phase_attempt
            or phase.integration_intent
            or phase.promotion_intent
        ):
            raise ValueError("Shared input producer phase is stale or uncertain")
        if not same_phase and phase.status != "accepted":
            raise ValueError("Cross-phase shared inputs require human phase acceptance")
        project = await executor.worktrees.owned_project(session.id)
        tree = await executor.verifier.tree(project, run.integrated_commit)
        artifacts, documents = {}, {}
        for path in paths:
            safe_path(path)
            if protected(path) or path not in producer.artifacts or path not in tree:
                raise ValueError("Shared publication path is not a declared safe artifact")
            blob = await executor.worktrees.git_bytes(project, "cat-file", "blob", tree[path][1])
            total += len(blob)
            if len(blob) > 2_000_000 or total > 16_000_000 or len(artifacts) >= 1024:
                raise ValueError("Shared publication exceeds artifact limits")
            digest = hashlib.sha256(blob).hexdigest()
            if (
                run.evidence.get("artifacts", {}).get(path) != digest
                or run.evidence.get("inventory", {}).get(path) != digest
            ):
                raise ValueError("Shared artifact differs from trusted integrated evidence")
            try:
                documents[path] = blob.decode("utf-8")
            except UnicodeError:
                raise ValueError(
                    "Shared input requires a qualified UTF-8 document; binary input is unsupported"
                ) from None
            artifacts[path] = digest
        result.append(
            SharedContractSnapshot(
                source_plan=session.planning.approval,
                ancestor_id=package.id.split("-W")[0] if same_phase else "root",
                producer_id=producer_id,
                consumer_id=package.id,
                producer_run_id=run.id,
                interface_name=interface[0],
                interface_version=interface[1],
                integrated_commit=run.integrated_commit,
                evidence_hash=content_hash(run.evidence),
                phase_attempt=run.phase_attempt,
                evidence_state="integrated" if same_phase else "accepted",
                artifacts=artifacts,
                documents=documents,
            )
        )
    return result


def rebuild_context(session, document, record, *, worker_limits=None):
    package = next(p for phase in document.phases for p in phase.packages if p.id == record.package_id)
    preflight_checks(package)
    packet = build_context(
        document,
        session.ledger,
        record.package_id,
        base_commit=record.base_commit,
        phase_attempt=record.phase_attempt,
        snapshots=record.snapshots,
        worker_limits=worker_limits,
    )
    if packet != record.packet:
        raise ValueError(
            "Saved execution context differs from current plan or instruction policy; review new inputs"
        )
    return packet


class ContextExecution:
    def context_limits(self):
        return {"per_session": self.scheduler.capacity, "global": self.scheduler.global_capacity}

    async def dispatch_preflight(self, run):
        """Recheck async Git and phase inputs before each external dispatch boundary."""
        self.check(run.id)
        phase = self.runs.phase(run.session_id, run.plan.content_hash, run.package_id.split("-W")[0])
        if (
            phase.status != "running"
            or phase.stale
            or phase.integration_intent
            or phase.promotion_intent
            or phase.attempt != run.phase_attempt
            or phase.staging_commit != run.base_commit
        ):
            raise ValueError("Approved context phase or input base changed before dispatch")
        project = await self.worktrees.owned_project(run.session_id)
        accepted = (await self.worktrees.git(project, "rev-parse", "refs/heads/accepted")).strip()
        if accepted != phase.base_commit:
            raise ValueError("Accepted project base changed before Codex dispatch")
        self.check(run.id)
        current = self.runs.phase(run.session_id, run.plan.content_hash, phase.phase_id)
        if (
            current.status != "running"
            or current.attempt != phase.attempt
            or current.stale
            or current.integration_intent
            or current.promotion_intent
            or current.base_commit != phase.base_commit
            or current.staging_commit != run.base_commit
        ):
            raise ValueError("Approved context base changed during dispatch preflight")

    async def prepare_context(self, session, identity, package_id, publications=()):
        document = self.guard(session, identity)
        eligible = self.scheduler.eligible(
            session.id, document, package_id.split("-W")[0], context_review=True
        )
        package = next((p for p in eligible if p.id == package_id), None)
        if package is None:
            raise ValueError("Context package is attempted, dependent, or in an ineligible phase")
        preflight_checks(package)
        for path in package.owned_paths:
            if protected(path):
                raise ValueError("Execution control files cannot be worker-owned paths")
        try:
            phase = self.runs.phase(session.id, identity.content_hash, package_id.split("-W")[0])
        except KeyError:
            phase = self.new_phase(session.id, identity, document, package_id.split("-W")[0])
        base = phase.staging_commit or await self.worktrees.prepare_base(session.id)
        snapshots = await published_snapshots(self, session, document, package, publications)
        current = self.sessions.get(session.id)
        self.guard(current, identity)
        # Recheck dependency eligibility and phase base after asynchronous Git reads.
        if package_id not in {
            p.id for p in self.scheduler.eligible(session.id, document, phase.phase_id, context_review=True)
        }:
            raise ValueError("Context eligibility changed while preparing inputs")
        try:
            saved = self.runs.phase(session.id, identity.content_hash, phase.phase_id)
            if saved.attempt != phase.attempt or saved.staging_commit not in {None, base}:
                raise ValueError("Context input base changed during preparation")
            if saved.staging_commit is None:

                def pin(p):
                    if p.stale or p.attempt != phase.attempt or p.staging_commit is not None:
                        raise ValueError("Context base changed before pinning")
                    p.base_commit = p.staging_commit = base

                self.runs.patch_phase(saved, pin)
        except KeyError:
            pass
        packet = build_context(
            document,
            current.ledger,
            package_id,
            base_commit=base,
            phase_attempt=phase.attempt,
            snapshots=snapshots,
            worker_limits=self.context_limits(),
        )
        return self.contexts.save(
            ContextRecord(
                session_id=session.id,
                plan=identity,
                package_id=package_id,
                phase_attempt=phase.attempt,
                base_commit=base,
                packet=packet,
                snapshots=snapshots,
            )
        )

    async def approve_context(self, session, identity, digest, packet_hash):
        document = self.guard(session, identity)
        record = self.contexts.get(session.id, digest)
        if record.plan != identity:
            raise ValueError("Execution context belongs to a different plan")
        package = next(p for phase in document.phases for p in phase.packages if p.id == record.package_id)
        if package.id not in {
            p.id
            for p in self.scheduler.eligible(
                session.id, document, package.id.split("-W")[0], context_review=True
            )
        }:
            raise ValueError("Context package is no longer eligible for approval")
        selections = [
            {
                "producer_id": s.producer_id,
                "interface_name": s.interface_name,
                "interface_version": s.interface_version,
                "paths": list(s.artifacts),
            }
            for s in record.snapshots
        ]
        snapshots = await published_snapshots(self, session, document, package, selections)
        if snapshots != record.snapshots:
            raise ValueError("Published shared inputs changed before context approval")
        project = await self.worktrees.owned_project(session.id)
        try:
            phase = self.runs.phase(session.id, identity.content_hash, package.id.split("-W")[0])
            base = phase.staging_commit
        except KeyError:
            phase = self.new_phase(session.id, identity, document, package.id.split("-W")[0])
            base = (
                phase.staging_commit
                or (await self.worktrees.git(project, "rev-parse", "refs/heads/accepted")).strip()
            )
        if phase.attempt != record.phase_attempt or base != record.base_commit:
            raise ValueError("Context base or phase attempt is stale; prepare a new packet")
        self.guard(self.sessions.get(session.id), identity)
        rebuild_context(session, document, record, worker_limits=self.context_limits())
        return self.contexts.approve(record, packet_hash)

    def check_context(self, run):
        if not run.context_hash:
            raise ContextReviewRequired(
                "Legacy run has no approved context; preserve it for manual settlement"
            )
        record = self.contexts.get(run.session_id, run.context_hash)
        if (
            not record.approved
            or record.plan != run.plan
            or record.package_id != run.package_id
            or record.phase_attempt != run.phase_attempt
            or record.base_commit != run.base_commit
            or record.packet.packet_hash != run.packet_hash
            or record.review_hash != run.context_review_hash
        ):
            raise ValueError("Run context identity or approval differs from its saved packet")
        session = self.sessions.get(run.session_id)
        document = self.guard(session, run.plan)
        rebuild_context(session, document, record, worker_limits=self.context_limits())
        for snapshot in record.snapshots:
            producer = self.runs.get(snapshot.producer_run_id)
            phase = self.runs.phase(run.session_id, run.plan.content_hash, producer.package_id.split("-W")[0])
            if (
                producer.session_id != run.session_id
                or producer.plan != run.plan
                or producer.package_id != snapshot.producer_id
                or producer.status != "integrated"
                or producer.stale
                or producer.cancel_requested
                or producer.integrated_commit != snapshot.integrated_commit
                or content_hash(producer.evidence) != snapshot.evidence_hash
                or producer.phase_attempt != snapshot.phase_attempt
                or phase.attempt != snapshot.phase_attempt
                or phase.stale
                or phase.integration_intent not in {None, run.id}
                or phase.promotion_intent
                or (snapshot.ancestor_id == "root" and phase.status != "accepted")
            ):
                raise ValueError("Published shared input is stale or its producer evidence changed")
        return record

    def approved_context(self, session, document, package_id, phase):
        base = phase.staging_commit
        if base is None:
            candidates = [
                r
                for r in self.contexts.list(session.id)
                if r.plan == session.planning.approval
                and r.package_id == package_id
                and r.phase_attempt == phase.attempt
                and r.approved
            ]
            if not candidates:
                raise ContextReviewRequired("Execution context review is required before package dispatch")
            base = candidates[0].base_commit
        record = self.contexts.approved_for(
            session.id, session.planning.approval, package_id, base, phase.attempt
        )
        try:
            rebuild_context(session, document, record, worker_limits=self.context_limits())
        except ValueError as error:
            raise ContextReviewRequired(
                "Context or instruction policy changed; prepare and review current inputs"
            ) from error
        return record

    def resume_context_phase(self, session, identity, phase_id, model=None):
        import asyncio

        if not self.dispatch_ready:
            raise ValueError("Startup reconciliation is still running")
        self.guard(session, identity)
        phase = self.runs.phase(session.id, identity.content_hash, phase_id)
        if phase.status != "awaiting_context_review" or phase.stale:
            raise ValueError("Phase is not awaiting context review")
        if phase.id in self.phase_tasks and not self.phase_tasks[phase.id].done():
            raise ValueError("Phase controller is still active")
        document = self.guard(session, identity)
        eligible = self.scheduler.eligible(session.id, document, phase_id, context_review=True)
        if not eligible:
            raise ValueError("No eligible contexts to resume")
        for package in eligible:
            self.approved_context(session, document, package.id, phase)

        def resume(p):
            if p.status != "awaiting_context_review" or p.stale or p.attempt != phase.attempt:
                raise ValueError("Phase changed before context resume")
            from .review import transition

            p.status, p.error = transition("phase", p.status, "running"), None

        phase = self.runs.patch_phase(phase, resume)
        self.phase_tasks[phase.id] = asyncio.create_task(self.drive_phase(phase, model))
        return phase
