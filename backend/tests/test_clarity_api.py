"""v2 approval, read-back and veto routes."""

from fastapi.testclient import TestClient

from backend.app.clarity.contracts import Decision
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.clarity_fixtures import reading_queue_session


def client_with(tmp_path, session):
    app = create_app(Settings(mode="live", database_path=str(tmp_path / "db")))
    session.mode = "live"
    app.state.store.save(session)
    return app


def run_clarity(client, session_id):
    data = client.post(f"/api/sessions/{session_id}/analyze").json()
    for field in data["clarity"]["fields"]:
        if field["failing"] == ["G3"]:
            data = client.post(
                f"/api/sessions/{session_id}/clarity/readback",
                json={
                    "field": field["field"],
                    "text_hash": field["text_hash"],
                    "revision": data["revision"],
                },
            ).json()
    return data


def test_new_session_version_defaults_and_override(tmp_path):
    with TestClient(create_app(Settings(mode="demo", database_path=str(tmp_path / "db")))) as client:
        assert client.post("/api/sessions", json={}).json()["clarity_version"] == 1
        assert client.post("/api/sessions", json={"clarity_version": 2}).json()["clarity_version"] == 2


def test_stale_read_back_is_refused(tmp_path):
    session = reading_queue_session()
    app = client_with(tmp_path, session)
    from backend.app.demo import DemoModels

    app.state.engine.models = DemoModels()
    with TestClient(app) as client:
        client.post(f"/api/sessions/{session.id}/analyze")
        response = client.post(
            f"/api/sessions/{session.id}/clarity/readback",
            json={"field": "job", "text_hash": "0" * 64, "revision": 1},
        )
        assert response.status_code == 409


def test_scenario_approval_replaces_playback_for_v2(tmp_path):
    session = reading_queue_session()
    app = client_with(tmp_path, session)
    from backend.app.demo import DemoModels

    app.state.engine.models = DemoModels()
    with TestClient(app) as client:
        data = run_clarity(client, session.id)
        assert data["gate"]["ready"], data["gate"]["blockers"]
        assert data["playback"] is None
        assert data["clarity_readout"]["scenarios"] >= 1
        approved = client.post(f"/api/sessions/{session.id}/approve", json={"revision": data["revision"]})
        assert approved.status_code == 200


def test_veto_turns_a_default_into_a_question(tmp_path):
    session = reading_queue_session()
    app = client_with(tmp_path, session)
    from backend.app.demo import DemoModels

    app.state.engine.models = DemoModels()
    with TestClient(app) as client:
        run_clarity(client, session.id)
        stored = app.state.store.get(session.id)
        stored.clarity.decisions = [
            Decision(
                id="D-x",
                status="delegated",
                question="What happens to duplicates?",
                options=["Allow", "Merge"],
                code_diff="Insert path versus merge path",
                context="c",
                drivers=["good"],
                kano="performance",
                category="behavior",
                reversibility="two-way",
                votes=[0, 0, 0, 1],
                outcome="Allow",
                owner="delegated",
                because="good: 3 of 4 candidate builds chose this",
            )
        ]
        app.state.store.save(stored)
        data = client.post(
            f"/api/sessions/{session.id}/clarity/veto",
            json={"decision_id": "D-x", "revision": stored.revision},
        ).json()
        assert data["vetoes"][0]["id"] == "V1"
        assert data["current_question"]["id"] == "V1"
        assert data["revision"] == stored.revision + 1
        assert (
            client.post(
                f"/api/sessions/{session.id}/clarity/veto",
                json={"decision_id": "D-missing", "revision": data["revision"]},
            ).status_code
            == 409
        )
