import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .builder import run_build, safe_index
from .demo import DemoModels
from .domain import Build, Session, gate_for, public_session
from .engine import Engine
from .models import LiveModels, ModelError
from .settings import Settings
from .store import Store


class Utterance(BaseModel):
    text: str = Field(min_length=1, max_length=6000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, text):
        if not text.strip():
            raise ValueError("Say or type an idea first.")
        return text.strip()


class Approval(BaseModel):
    revision: int = Field(ge=0)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    store = Store(settings.database_path)
    models = DemoModels() if settings.mode == "demo" else LiveModels(settings)
    engine = Engine(store, models)
    locks = defaultdict(asyncio.Lock)
    jobs: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        for task in jobs:
            task.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        await models.close()

    app = FastAPI(title="Prompt Caller", lifespan=lifespan)
    app.state.engine = engine
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin
            not in {
                "http://127.0.0.1:3000",
                "http://localhost:3000",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            }
        ):
            return HTMLResponse("Origin not allowed", status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def load(id):
        try:
            return store.get(id)
        except KeyError:
            raise HTTPException(404, "Session not found") from None

    def guard_edit(session):
        if session.mode != settings.mode:
            raise HTTPException(409, "This session uses a different mode. Start a new conversation.")
        if session.build.status == "running":
            raise HTTPException(409, "Wait for the current build to finish.")

    @app.exception_handler(ModelError)
    async def model_error(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "models_configured": bool(settings.nebius_api_key and settings.nebius_api_key.get_secret_value()),
            "build_enabled": settings.allow_claude_build,
            "agent": "Claude Code",
        }

    @app.get("/api/sessions")
    async def sessions():
        return store.list()

    @app.post("/api/sessions")
    async def new_session():
        session = Session(mode=settings.mode)
        store.save(session)
        return public_session(session)

    @app.get("/api/sessions/{id}")
    async def get_session(id: str):
        return public_session(load(id))

    @app.post("/api/sessions/{id}/turns")
    async def turn(id: str, utterance: Utterance):
        guard_edit(load(id))

        async def events():
            async with locks[id]:
                session = load(id)
                if session.build.status == "running":
                    yield 'data: {"type":"error","message":"A build is running."}\n\n'
                    return
                try:
                    async for event in engine.turn(session, utterance.text):
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                finally:
                    store.save(session)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/sessions/{id}/analyze")
    async def analyze(id: str):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            if not session.turns:
                raise HTTPException(409, "Describe your idea first.")
            await engine.extract_latest(session)
            async for _ in engine.analyze(session):
                pass
            return public_session(session)

    @app.post("/api/sessions/{id}/playback")
    async def playback(id: str):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            if not session.ledger:
                raise HTTPException(409, "Describe your idea first.")
            await engine.playback(session)
            return public_session(session)

    @app.post("/api/sessions/{id}/approve")
    async def approve(id: str, approval: Approval):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            if (
                not gate_for(session).ready
                or session.playback_revision != session.revision
                or approval.revision != session.revision
            ):
                raise HTTPException(
                    409, "Review the current playback after the understanding meter is ready."
                )
            session.approved_revision = session.revision
            store.save(session)
            return public_session(session)

    @app.post("/api/sessions/{id}/compile")
    async def compile_brief(id: str):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            if not gate_for(session).ready or session.approved_revision != session.revision:
                raise HTTPException(409, "Approve the current playback before compiling.")
            await engine.compile(session)
            return public_session(session)

    @app.post("/api/sessions/{id}/build")
    async def build(id: str):
        async with locks[id]:
            session = load(id)
            guard_edit(session)
            if (
                not session.brief
                or session.approved_revision != session.revision
                or not gate_for(session).ready
            ):
                raise HTTPException(409, "Compile an approved brief before building.")
            if session.mode == "live" and not settings.allow_claude_build:
                raise HTTPException(409, "Set ALLOW_CLAUDE_BUILD=true in the server .env to run Claude Code.")
            session.build = Build(status="running", demo=session.mode == "demo")
            store.save(session)
            job = asyncio.create_task(run_build(settings, store, session))
            jobs.add(job)
            job.add_done_callback(jobs.discard)
            return public_session(session)

    @app.get("/api/sessions/{id}/brief")
    async def download_brief(id: str):
        session = load(id)
        if not session.brief:
            raise HTTPException(404, "Compile a brief first.")
        return HTMLResponse(
            session.brief.markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="CLAUDE.md"'},
        )

    @app.get("/api/sessions/{id}/preview")
    async def preview(id: str, download: bool = False):
        session = load(id)
        if session.build.status != "complete":
            raise HTTPException(404, "No completed build is available.")
        try:
            index = safe_index(settings, session)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(404, str(error)) from None
        if download:
            return FileResponse(index, filename="index.html", media_type="text/html")
        return HTMLResponse(
            index.read_text(encoding="utf-8"),
            headers={
                "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; "
                "form-action 'none'; sandbox allow-scripts",
                "Cache-Control": "no-store",
            },
        )

    return app


app = create_app()
