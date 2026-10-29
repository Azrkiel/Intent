"""Human context review endpoints, separate from plan and phase acceptance."""

from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import Field

from ..planning.contracts import PlanApproval, PlanningModel
from ..planning.worker_bundle import export_worker_bundle
from .context import rebuild_context


class PublicationSelection(PlanningModel):
    producer_id: str = Field(min_length=1, max_length=80)
    interface_name: str | None = Field(default=None, max_length=40)
    interface_version: str | None = Field(default=None, max_length=2000)
    paths: list[str] = Field(min_length=1, max_length=1024)


class PrepareContext(PlanApproval):
    package_id: str = Field(min_length=1, max_length=80)
    publications: list[PublicationSelection] = Field(default_factory=list, max_length=80)


class ApproveContext(PlanApproval):
    packet_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def current_context(executor, session, document, record):
    if record.plan != session.planning.approval or record.plan != session.planning.active:
        return False
    try:
        eligible = executor.scheduler.eligible(
            session.id, document, record.package_id.split("-W")[0], context_review=True
        )
        if record.package_id not in {p.id for p in eligible}:
            return False
        try:
            phase = executor.runs.phase(
                session.id, record.plan.content_hash, record.package_id.split("-W")[0]
            )
        except KeyError:
            phase = executor.new_phase(session.id, record.plan, document, record.package_id.split("-W")[0])
        if phase.attempt != record.phase_attempt or phase.staging_commit not in {None, record.base_commit}:
            return False
        executor.guard(session, record.plan)
        rebuild_context(session, document, record, worker_limits=executor.context_limits())
        return True
    except (ValueError, KeyError):
        return False


def package_context_options(executor, session, document, phase_id):
    try:
        eligible = {
            p.id for p in executor.scheduler.eligible(session.id, document, phase_id, context_review=True)
        }
        reason = ""
        executor.guard(session, session.planning.approval)
    except (ValueError, KeyError):
        eligible, reason = set(), "Plan or dependency gates are not ready for context review"
    packages = {p.id: p for phase in document.phases for p in phase.packages}
    runs = {
        r.package_id: r for r in executor.runs.current_runs(session.id) if r.plan == session.planning.approval
    }
    records = executor.contexts.list(session.id)
    options = {}
    for package in next(p.packages for p in document.phases if p.id == phase_id):
        publications = []
        for dependency in document.dependency_ids[package.id]:
            producer = packages[dependency]
            run = runs.get(dependency)
            artifacts = []
            if run and run.status == "integrated" and not run.stale and not run.cancel_requested:
                artifacts = [
                    {"path": path, "sha256": run.evidence["artifacts"][path]}
                    for path in producer.artifacts
                    if path in run.evidence.get("artifacts", {})
                ]
            interfaces = [i for i in package.consumes if any(i == produced for produced in producer.produces)]
            for interface in interfaces or [None]:
                publications.append(
                    {
                        "producer_id": dependency,
                        "interface_name": interface.name if interface else None,
                        "interface_version": interface.version if interface else None,
                        "artifacts": artifacts,
                    }
                )
        ready = any(
            r.package_id == package.id and r.approved and current_context(executor, session, document, r)
            for r in records
        )
        options[package.id] = {
            "can_prepare": package.id in eligible,
            "context_ready": ready,
            "context_reason": reason
            if package.id not in eligible
            else ("" if ready else "Review exact package inputs before dispatch"),
            "publication_options": publications,
        }
    return options


def context_review_routes(router, executor, locks, load):
    @router.post("/contexts/prepare")
    async def prepare_context(id: str, request: PrepareContext):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(request.model_dump(exclude={"package_id", "publications"}))
            try:
                record = await executor.prepare_context(
                    session, identity, request.package_id, [p.model_dump() for p in request.publications]
                )
                return record.public() | {"current": True}
            except (ValueError, KeyError) as error:
                raise HTTPException(409, str(error)) from None

    @router.post("/contexts/{context_hash}/approve")
    async def approve_context(id: str, context_hash: str, request: ApproveContext):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(request.model_dump(exclude={"packet_hash"}))
            try:
                record = await executor.approve_context(session, identity, context_hash, request.packet_hash)
                return record.public() | {"current": True}
            except (ValueError, KeyError) as error:
                raise HTTPException(409, str(error)) from None

    @router.get("/contexts/{context_hash}/bundle")
    async def worker_bundle(id: str, context_hash: str):
        async with locks[id]:
            session = load(id)
            try:
                document = executor.guard(session, session.planning.approval)
                record = executor.contexts.get(id, context_hash)
                if not record.approved or not current_context(executor, session, document, record):
                    raise ValueError("Approve the current exact worker context before export")
                return Response(
                    export_worker_bundle(record.packet),
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": 'attachment; filename="worker-context.zip"',
                        "Cache-Control": "no-store",
                    },
                )
            except (ValueError, KeyError) as error:
                raise HTTPException(409, str(error)) from None
