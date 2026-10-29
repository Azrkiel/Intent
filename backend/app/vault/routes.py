import zipfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from .archive import MAX_ARCHIVE_BYTES, export_vault, import_vault
from .contracts import RevisionRequest, SaveRequest, Vault
from .seed import seed_vault
from .store import VaultConflict, VaultStore


def vault_router(store, planner, locks, load, guard_edit):
    router = APIRouter(prefix="/api/sessions/{id}/vault")
    vaults = VaultStore(store)

    def save(session, expected, vault):
        try:
            return vaults.save(session.id, expected, vault)
        except VaultConflict as error:
            raise HTTPException(409, str(error)) from None

    @router.get("")
    async def get_vault(id: str):
        return vaults.get(load(id))

    @router.post("")
    async def save_vault(id: str, body: SaveRequest):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            current = vaults.get(session)
            return save(
                session,
                body.expected_revision,
                Vault(**current.model_dump(exclude={"notes"}), notes=body.notes),
            )

    @router.post("/seed")
    async def seed(id: str, body: RevisionRequest):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            state = session.planning
            partial = not state.active
            if state.active:
                plan = store.get_plan(id, state.active.plan_id, state.active.revision)
            elif state.attempts and state.attempts[-1].outline:
                plan = planner.document(session, state.attempts[-1])
            else:
                raise HTTPException(409, "Generate a phase plan first, or write notes manually.")
            try:
                vault = seed_vault(vaults.get(session), plan, partial=partial)
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            return save(session, body.expected_revision, vault)

    @router.get("/export")
    async def export(id: str):
        return Response(
            export_vault(vaults.get(load(id))),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="intent-vault.zip"',
                "Cache-Control": "no-store",
            },
        )

    @router.post("/import")
    async def import_notes(id: str, request: Request, expected_revision: int = Query(ge=0)):
        session = load(id)
        guard_edit(session)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_ARCHIVE_BYTES:
                raise HTTPException(413, "ZIP exceeds the 3 MB upload limit")
        try:
            vault = import_vault(bytes(data), demo=session.mode == "demo")
        except (
            ValueError,
            zipfile.BadZipFile,
            RuntimeError,
            NotImplementedError,
            OSError,
            KeyError,
            TypeError,
        ) as error:
            raise HTTPException(422, "Invalid Markdown vault: " + str(error)[:200]) from None
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            return save(session, expected_revision, vault)

    return router
