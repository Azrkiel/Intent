import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(
            Settings(
                database_path=str(tmp_path / "sessions.db"), build_root=str(tmp_path / "builds"), mode="demo"
            )
        )
    ) as client:
        yield client


def send(client, id, text):
    response = client.post(f"/api/sessions/{id}/turns", json={"text": text})
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert not any(x["type"] == "error" for x in events), events
    return client.get(f"/api/sessions/{id}").json()


def test_demo_runs_contradiction_to_approved_cited_brief(client):
    session = client.post("/api/sessions", json={}).json()
    id = session["id"]
    session = send(
        client,
        id,
        "I want a habit tracker, no login, saved across my phone and laptop, "
        "and reminders should be automatic.",
    )
    assert session["current_question"]["lens"] == "contradictions"
    assert not session["gate"]["ready"]
    assert client.post(f"/api/sessions/{id}/compile").status_code == 409
    for _ in range(10):
        if session["gate"]["ready"]:
            break
        question = session["current_question"]
        assert question
        session = send(client, id, question["options"][0])
    assert session["gate"]["ready"], session
    assert (
        client.post(f"/api/sessions/{id}/approve", json={"revision": session["revision"]}).status_code == 409
    )
    assert client.post(f"/api/sessions/{id}/playback").status_code == 200
    assert (
        client.post(f"/api/sessions/{id}/approve", json={"revision": session["revision"]}).status_code == 200
    )
    compiled = client.post(f"/api/sessions/{id}/compile")
    assert compiled.status_code == 200, compiled.text
    assert "[L" in compiled.json()["brief"]["markdown"]
    assert client.get(f"/api/sessions/{id}").json()["brief"]
    edited = send(client, id, "Actually, make this device only for now")
    assert edited["approved_revision"] is None
    assert edited["brief"] is None


def test_blank_input_unknown_session_and_live_build_guard(client):
    assert client.get("/api/sessions/missing").status_code == 404
    session = client.post("/api/sessions", json={}).json()
    assert client.post(f"/api/sessions/{session['id']}/turns", json={"text": "  "}).status_code == 422
    assert client.post(f"/api/sessions/{session['id']}/build").status_code == 409


def test_database_persists_sessions_and_reports_mode(client):
    first = client.post("/api/sessions", json={}).json()
    assert first["mode"] == "demo"
    assert client.get("/api/sessions").json()[0]["id"] == first["id"]
    health = client.get("/api/health").json()
    assert health["mode"] == "demo"
    assert "api_key" not in health
