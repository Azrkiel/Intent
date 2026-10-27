from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from ..codex.protocol import CodexError
from ..planning.contracts import PlanApproval, PlanningModel


class StartExecution(PlanApproval):
    package_id: str = Field(min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class EmptyRequest(PlanningModel):
    pass


class PermissionDecision(PlanningModel):
    decision: Literal["accept", "decline", "cancel"]
    generation: str = Field(min_length=1, max_length=80)


def execution_router(executor, locks, load):
    router = APIRouter(prefix="/api/sessions/{id}/execution")

    @router.get("")
    async def detail(id: str):
        load(id)
        return {
            "runs": [run.public() for run in executor.runs.list(id)],
            "execution_enabled": executor.settings.allow_codex_execution,
            "phase_acceptance_enabled": False,
        }

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
