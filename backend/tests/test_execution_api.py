import asyncio

import httpx

from backend.app.main import create_app
from backend.tests.test_codex_worker import fixture


async def test_single_package_api_guards_and_preserves_run_on_restart(tmp_path):
    session, document, executor = fixture(tmp_path)
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        base = f"/api/sessions/{session.id}/execution"
        request = {**session.planning.approval.model_dump(), "package_id": document.phases[0].packages[0].id}
        assert (await client.post(base, json={**request, "content_hash": "b" * 64})).status_code == 409
        assert (await client.post(base, json={**request, "sandbox": "all"})).status_code == 422
        started = await client.post(base, json=request)
        assert started.status_code == 200, started.text
        run_id = started.json()["id"]
        await app.state.executor.tasks[run_id]
        runs = (await client.get(base)).json()["runs"]
        assert runs[0]["status"] == "verifying"
        assert "account_fingerprint" not in runs[0]
        assert (await client.post(base, json=request)).status_code == 409
        assert (
            await client.post(f"/api/sessions/missing/execution/{run_id}/cancel", json={})
        ).status_code == 404
        assert (await client.post(base + "/missing/cancel", json={})).status_code == 404
    restored = create_app(executor.settings, codex_factory=executor.factory)
    assert restored.state.executor.runs.get(run_id).status == "verifying"


async def test_default_feature_flag_and_demo_guard_prevent_dispatch(tmp_path):
    session, document, executor = fixture(tmp_path)
    executor.settings.allow_codex_execution = False
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        base = f"/api/sessions/{session.id}/execution"
        request = {**session.planning.approval.model_dump(), "package_id": document.phases[0].packages[0].id}
        assert (await client.post(base, json=request)).status_code == 409
        assert not app.state.executor.runs.list(session.id)
    executor.settings.allow_codex_execution = True
    executor.settings.mode = session.mode = "demo"
    executor.sessions.save(session)
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        assert (await client.post(base, json=request)).status_code == 409


async def test_correction_interrupts_execution_and_stops_stale_permission_replies(tmp_path):
    session, document, executor = fixture(tmp_path, "approval")
    executor.settings.nebius_api_key = None
    app = create_app(executor.settings, codex_factory=executor.factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        base = f"/api/sessions/{session.id}/execution"
        request = {**session.planning.approval.model_dump(), "package_id": document.phases[0].packages[0].id}
        run = (await client.post(base, json=request)).json()
        for _ in range(100):
            saved = app.state.executor.runs.get(run["id"])
            if saved.approvals:
                break
            await asyncio.sleep(0.02)
        await client.post(f"/api/sessions/{session.id}/turns", json={"text": "A new requirement"})
        stale = app.state.executor.runs.get(run["id"])
        assert stale.status == "blocked" and stale.stale
        permission = saved.approvals[0]
        response = await client.post(
            base + f"/{run['id']}/approvals/{permission.id}",
            json={"generation": saved.generation, "decision": "accept"},
        )
        assert response.status_code == 409
