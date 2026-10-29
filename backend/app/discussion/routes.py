from fastapi import APIRouter, HTTPException, Query

from .contracts import DiscussionRequest


def discussion_router(service, locks, load):
    router = APIRouter(prefix="/api/sessions/{id}/discussion")

    @router.get("")
    async def view(id: str, node_id: str = Query(default="root", min_length=1, max_length=120)):
        try:
            return service.view(load(id), node_id)
        except KeyError as error:
            raise HTTPException(404, str(error)) from None
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("")
    async def submit(id: str, request: DiscussionRequest):
        load(id)
        async with locks[id]:
            try:
                return await service.submit(id, request)
            except KeyError as error:
                raise HTTPException(404, str(error)) from None
            except ValueError as error:
                raise HTTPException(409, str(error)) from None

    return router
