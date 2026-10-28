import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from .contracts import PlanApproval, PlanningModel
from .export import export_bundle
from .graph import project_attempt, project_graph
from .render import render_engineering, render_human
from .validation import validate_plan


class PlanRequest(PlanningModel):
    pass


def planning_router(store, service, locks, load, guard_edit):
    router = APIRouter(prefix="/api/sessions/{id}/plan")

    def guard(session):
        guard_edit(session)
        try:
            service.guard(session)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    def detail(session):
        state = session.planning
        document = None
        partial = False
        if state.active:
            document = store.get_plan(session.id, state.active.plan_id, state.active.revision)
        elif state.attempts and state.attempts[-1].outline:
            attempt = state.attempts[-1]
            partial = True
            document = service.document(session, attempt)
        worker_limits = {
            "per_session": service.settings.codex_max_workers,
            "global": service.settings.codex_global_max_workers,
        }
        graph = None
        if document and not partial:
            graph = project_graph(document, state=state.status, worker_limits=worker_limits)
        elif partial:
            graph = project_attempt(
                state.attempts[-1], session.ledger, mode=session.mode, state=state.status,
                current_revision=session.revision, worker_limits=worker_limits,
            )
        return {
            "session_id": session.id,
            "requirements_revision": session.revision,
            "planning": state.public(),
            "plan": document.model_dump(mode="json") if document and not partial else None,
            "views": {"human": render_human(document), "engineering": render_engineering(document)}
            if document
            else None,
            "partial": partial,
            "graph": graph,
            "execution_enabled": False,
            "attempt_limit": service.attempt_limit(session),
            "pass_limit": service.settings.planning_max_passes,
            "estimated_usd": round(sum(x.estimated_usd for x in session.usage), 6),
            "usage": [x.model_dump() for x in session.usage if x.role.startswith("planner:")],
        }

    @router.get("")
    async def get_plan(id: str):
        return detail(load(id))

    @router.post("")
    async def generate(id: str, request: PlanRequest):
        session = load(id)
        guard(session)
        if locks[id].locked():
            raise HTTPException(409, "This conversation has an active operation")
        if (
            session.planning.status not in {"review_ready", "approved"}
            and len(session.planning.attempts) >= service.attempt_limit(session)
        ):
            raise HTTPException(409, "Planning attempt allowance exhausted for this session")

        async def events():
            async with locks[id]:
                session = load(id)
                # Recheck after acquiring the shared session lock.
                generator = service.generate(session)
                try:
                    guard(session)
                    async for event in generator:
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                except (ValueError, HTTPException) as error:
                    message = error.detail if isinstance(error, HTTPException) else str(error)
                    yield "data: " + json.dumps(service.event(session, "plan_error", message)) + "\n\n"
                finally:
                    await generator.aclose()
                yield 'data: {"type":"done"}\n\n'

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/approve")
    async def approve(id: str, approval: PlanApproval):
        async with locks[id]:
            session = load(id)
            guard(session)
            state = session.planning
            if state.status not in {"review_ready", "approved"} or state.active != approval:
                raise HTTPException(409, "Review the current complete plan before approving")
            document = store.get_plan(id, approval.plan_id, approval.revision)
            if (
                approval.requirements_revision != session.revision
                or document.content_hash != approval.content_hash
            ):
                raise HTTPException(409, "Plan approval is stale")
            try:
                validate_plan(document, session.ledger)
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            state.status, state.approval = "approved", approval
            store.save(session)
            return detail(session)

    @router.get("/bundle")
    async def bundle(id: str):
        async with locks[id]:
            session = load(id)
            guard(session)
            state = session.planning
            if state.status != "approved" or not state.approval or state.active != state.approval:
                raise HTTPException(409, "Approve the current complete plan before export")
            document = store.get_plan(id, state.active.plan_id, state.active.revision)
            try:
                data = export_bundle(
                    document, state.approval, session.revision, session.ledger,
                    worker_limits={
                        "per_session": service.settings.codex_max_workers,
                        "global": service.settings.codex_global_max_workers,
                    },
                )
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            return Response(
                data,
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="project-plan.zip"',
                    "Cache-Control": "no-store",
                },
            )

    return router
