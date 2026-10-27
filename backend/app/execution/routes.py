import hashlib
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import Field

from ..codex.protocol import CodexError
from ..planning.contracts import PlanApproval, PlanningModel


class StartExecution(PlanApproval):
    package_id: str = Field(min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class EmptyRequest(PlanningModel):
    pass


class StartPhase(PlanApproval):
    model: str | None = Field(default=None, min_length=1, max_length=200)


class PermissionDecision(PlanningModel):
    decision: Literal["accept", "decline", "cancel"]
    generation: str = Field(min_length=1, max_length=80)


class ReviewDecision(PlanApproval):
    decision: Literal["accept", "reject"]
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes: str = Field(default="", max_length=2000)


class RepairPhase(StartPhase):
    evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attempt: int = Field(ge=1)


class ReconcilePhase(PlanApproval):
    evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


def execution_router(executor, locks, load):
    router = APIRouter(prefix="/api/sessions/{id}/execution")

    @router.get("")
    async def detail(id: str):
        session = load(id)
        phases = executor.runs.phases(id)
        identity = session.planning.active
        document = executor.sessions.get_plan(id, identity.plan_id, identity.revision) if identity else None
        eligible = {}
        if document:
            for phase in document.phases:
                try:
                    executor.guard(session, identity)
                    eligible[phase.id] = {
                        "can_start": bool(executor.scheduler.eligible(id, document, phase.id)),
                        "reason": "",
                    }
                    if any(p.phase_id == phase.id and p.plan == identity for p in phases):
                        eligible[phase.id] = {
                            "can_start": False,
                            "reason": "Phase already started; review or repair",
                        }
                except (ValueError, CodexError) as error:
                    eligible[phase.id] = {"can_start": False, "reason": str(error)}
        return {
            "session_id": id,
            "requirements_revision": session.revision,
            "plan": identity.model_dump() if identity else None,
            "runs": [run.public() for run in executor.runs.list(id)],
            "phases": [phase.model_dump(mode="json") for phase in phases],
            "reviews": [executor.runs.review(p.review_hash).public() for p in phases if p.review_hash],
            "phase_options": [
                {
                    "id": p.id,
                    "title": document.outline.phases[i].title,
                    "packages": [{"id": w.id, "owned_paths": w.owned_paths} for w in p.packages],
                    **eligible[p.id],
                }
                for i, p in enumerate(document.phases)
            ]
            if document
            else [],
            "execution_enabled": executor.settings.allow_codex_execution,
            "max_workers": executor.scheduler.capacity,
            "verification_policy": "git-inspection-only-v1",
            "phase_acceptance_enabled": True,
            "simulation": False,
        }

    @router.post("/phases/{phase_id}/review")
    async def review_phase(id: str, phase_id: str, request: ReviewDecision):
        async with locks[id]:
            load(id)
            identity = PlanApproval.model_validate(
                request.model_dump(exclude={"decision", "evidence_hash", "notes"})
            )
            try:
                phase = await executor.review_phase(
                    id, identity, phase_id, request.evidence_hash, request.decision, request.notes
                )
                return phase.model_dump(mode="json")
            except (KeyError, ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None

    @router.get("/phases/{phase_id}/artifacts/{path:path}")
    async def artifact(id: str, phase_id: str, path: str, evidence_hash: str):
        load(id)
        try:
            review = executor.runs.review(evidence_hash).public()
            phase = executor.runs.phase(id, review["plan"]["content_hash"], phase_id)
            expected = review["evidence"]["artifacts"].get(path)
            if not expected or review["phase_execution_id"] != phase.id or review["phase_id"] != phase_id:
                raise ValueError("Artifact does not belong to this phase review")
            project = await executor.worktrees.owned_project(id)
            tree = await executor.verifier.tree(project, review["staging_commit"])
            data = await executor.worktrees.git_bytes(project, "cat-file", "blob", tree[path][1])
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Artifact bytes differ from review evidence")
            return Response(
                data,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": "attachment; filename*=UTF-8''" + quote(PurePosixPath(path).name),
                    "Content-Security-Policy": "default-src 'none'; sandbox",
                    "Cache-Control": "no-store",
                },
            )
        except (KeyError, ValueError, CodexError):
            raise HTTPException(404, "Reviewed artifact is unavailable") from None

    @router.post("/phases/{phase_id}/repair")
    async def repair_phase(id: str, phase_id: str, request: RepairPhase):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(
                request.model_dump(exclude={"model", "evidence_hash", "attempt"})
            )
            try:
                phase = executor.repair_phase(
                    session, identity, phase_id, request.evidence_hash, request.model, request.attempt
                )
                return phase.model_dump(mode="json")
            except (KeyError, ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None

    @router.post("/phases/{phase_id}/start")
    async def start_phase(id: str, phase_id: str, request: StartPhase):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(request.model_dump(exclude={"model"}))
            try:
                phase = executor.start_phase(session, identity, phase_id, request.model)
            except (ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None
            return phase.model_dump(mode="json")

    @router.post("/phases/{phase_id}/cancel")
    async def cancel_phase(id: str, phase_id: str, request: PlanApproval):
        async with locks[id]:
            load(id)
            try:
                return (await executor.cancel_phase(id, request, phase_id)).model_dump(mode="json")
            except (KeyError, ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None

    @router.post("/phases/{phase_id}/reconcile")
    async def reconcile_phase(id: str, phase_id: str, request: ReconcilePhase):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(request.model_dump(exclude={"evidence_hash"}))
            try:
                return (
                    await executor.reconcile_phase(session, identity, phase_id, request.evidence_hash)
                ).model_dump(mode="json")
            except (KeyError, ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None

    @router.post("/{run_id}/verify")
    async def verify(id: str, run_id: str, request: PlanApproval):
        load(id)
        try:
            run = executor.owned(id, run_id)
            if run.plan != request:
                raise ValueError("Verification requires the current run's exact plan identity")
            return (await executor.verify_run(id, run_id)).public()
        except KeyError:
            raise HTTPException(404, "Execution run not found") from None
        except (ValueError, CodexError) as error:
            raise HTTPException(409, str(error)) from None

    @router.post("")
    async def start(id: str, request: StartExecution):
        async with locks[id]:
            session = load(id)
            identity = PlanApproval.model_validate(request.model_dump(exclude={"package_id", "model"}))
            try:
                run = executor.start(session, identity, request.package_id, request.model)
            except (ValueError, CodexError) as error:
                raise HTTPException(409, str(error)) from None
            return run.public()

    @router.post("/{run_id}/cancel")
    async def cancel(id: str, run_id: str, request: EmptyRequest):
        load(id)
        try:
            return (await executor.cancel(id, run_id)).public()
        except KeyError:
            raise HTTPException(404, "Execution run not found") from None
        except (ValueError, CodexError) as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{run_id}/approvals/{request_id}")
    async def decide(id: str, run_id: str, request_id: str, request: PermissionDecision):
        load(id)
        try:
            await executor.decide(id, run_id, request_id, request.decision, request.generation)
            return executor.owned(id, run_id).public()
        except KeyError:
            raise HTTPException(404, "Execution run or permission request not found") from None
        except (ValueError, CodexError) as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{run_id}/reconcile")
    async def reconcile(id: str, run_id: str, request: EmptyRequest):
        load(id)
        try:
            return (await executor.reconcile(id, run_id, wait=False)).public()
        except KeyError:
            raise HTTPException(404, "Execution run not found") from None
        except (ValueError, CodexError) as error:
            raise HTTPException(409, str(error)) from None

    return router
