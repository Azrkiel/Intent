import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.planning_fixtures import ready_session


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "sessions.db"), mode="demo"))
    with TestClient(app) as client:
        session = ready_session()
        app.state.store.save(session)
        yield client, session


def generate(client, session):
    response = client.post(f"/api/sessions/{session.id}/plan", json={})
    assert response.status_code == 200, response.text
    events = [json.loads(x[6:]) for x in response.text.splitlines() if x.startswith("data: ")]
    assert events[-1]["type"] == "done"
    assert not any(e["type"] == "plan_error" for e in events), events
    return client.get(f"/api/sessions/{session.id}/plan").json()


def test_generate_approve_export_restore_and_correction(client):
    client, session = client
    root = f"/api/sessions/{session.id}/plan"
    assert client.get(root + "/bundle").status_code == 409
    state = generate(client, session)
    assert state["execution_enabled"] is False
    assert state["planning"]["status"] == "review_ready"
    assert state["plan"]["content_hash"] in state["views"]["human"]
    accepted = state["planning"]["active"]
    assert client.post(root + "/approve", json={**accepted, "requirements_revision": 0}).status_code == 409
    assert client.post(root + "/approve", json=accepted).status_code == 200
    response = client.get(root + "/bundle")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "DEMO" in archive.read("VISION.md").decode()
    restored = client.get(root).json()
    assert restored["planning"]["approval"] == accepted
    client.post(f"/api/sessions/{session.id}/turns", json={"text": "Use browser storage only"})
    assert client.get(root).json()["planning"]["status"] == "stale"
    assert client.get(root + "/bundle").status_code == 409
    assert client.post(root + "/approve", json=accepted).status_code == 409


def test_guarded_routes(client):
    client, session = client
    assert client.get("/api/sessions/missing/plan").status_code == 404
    assert client.post(f"/api/sessions/{session.id}/plan", json={"permission": "all"}).status_code == 422
    assert client.post(f"/api/sessions/{session.id}/plan/approve", json={}).status_code == 422
    session.approved_revision = None
    client.app.state.store.save(session)
    assert client.post(f"/api/sessions/{session.id}/plan", json={}).status_code == 409


def test_restart_marks_planning_interrupted_and_preserves_pass_reservations(client):
    client, session = client
    from backend.app.planning.contracts import PlanAttempt

    session.planning.status = "planning"
    session.planning.attempts = [
        PlanAttempt(plan_id="interrupted", revision=1, requirements_revision=1, passes=["planner:outline"])
    ]
    client.app.state.store.save(session)
    client.app.state.store.recover()
    restored = client.app.state.store.get(session.id)
    assert restored.planning.status == "blocked"
    assert restored.planning.attempts[0].passes == ["planner:outline"]
