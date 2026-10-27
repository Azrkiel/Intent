import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.demo import DemoModels
from backend.app.domain import Candidate, Session, Turn, public_session
from backend.app.engine import Engine
from backend.app.main import create_app
from backend.app.models import ModelError
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.test_ledger import ready_session


async def test_failed_critic_keeps_the_gate_closed_and_preserves_ledger(tmp_path):
    class FailingCritic(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "critic:edges":
                raise ModelError("Timeout")
            return await super().call(session, role, schema, instruction, payload)

    store = Store(str(tmp_path / "sessions.db"))
    session = ready_session()
    store.save(session)
    async for _ in Engine(store, FailingCritic()).analyze(session):
        pass
    restored = store.get(session.id)
    assert not public_session(restored)["gate"]["ready"]
    assert len(restored.ledger) == 6
    assert any("edges" in warning for warning in restored.warnings)


def test_retry_analysis_reextracts_a_failed_user_correction(tmp_path):
    class OnceFailingExtractor(DemoModels):
        failed = False

        async def call(self, session, role, schema, instruction, payload):
            if role == "extractor" and not self.failed:
                self.failed = True
                raise ModelError("Extraction timed out")
            return await super().call(session, role, schema, instruction, payload)

    settings = Settings(mode="demo", database_path=str(tmp_path / "db"))
    app = create_app(settings)
    app.state.engine.models = OnceFailingExtractor()
    with TestClient(app) as client:
        session = ready_session()
        session.turns = [Turn(number=1, text="Original idea")]
        app.state.store.save(session)
        result = client.post(f"/api/sessions/{session.id}/turns", json={"text": "Actually, this device only"})
        assert "Extraction timed out" in result.text
        retry = client.post(f"/api/sessions/{session.id}/analyze")
        assert retry.status_code == 200
        data = retry.json()
        assert any(item["source"] == "Actually, this device only" for item in data["ledger"])


async def test_unanswered_low_impact_questions_are_preserved_as_undecided(tmp_path):
    session = ready_session()
    session.candidates = [
        Candidate(
            id="Q1",
            lens="edges",
            question="Should offline edits be queued?",
            options=["Queue for later", "Disable editing offline"],
            targets=["L3"],
            code_diff="A persistent outbox vs a connection guard",
            divergence=2,
            uncertainty=1,
            cost_to_change=2,
        )
    ]
    store = Store(str(tmp_path / "db"))
    await Engine(store, DemoModels()).compile(session)
    assert any(line.section == "Undecided" and "offline" in line.text for line in session.brief.lines)


def test_preview_is_sandboxed_and_build_writes_the_approved_brief(tmp_path):
    settings = Settings(mode="demo", database_path=str(tmp_path / "db"), build_root=str(tmp_path / "builds"))
    app = create_app(settings)
    with TestClient(app) as client:
        session = ready_session()
        session.approved_revision = session.revision
        app.state.store.save(session)
        assert client.post(f"/api/sessions/{session.id}/compile").status_code == 200
        assert client.post(f"/api/sessions/{session.id}/build").status_code == 200
        # Demo build has no awaits, so it completes before the next request.
        built = client.get(f"/api/sessions/{session.id}").json()
        assert built["build"]["status"] == "complete"
        assert Path(built["build"]["directory"], "CLAUDE.md").exists()
        response = client.get(f"/api/sessions/{session.id}/preview")
        assert response.status_code == 200
        assert "sandbox allow-scripts" in response.headers["content-security-policy"]
        assert "connect-src 'none'" in response.headers["content-security-policy"]
        assert "prebuilt" in response.text.lower()


def test_browser_origin_cannot_submit_mutations_from_an_unrelated_website(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "db")))
    with TestClient(app) as client:
        response = client.post("/api/sessions", json={}, headers={"Origin": "https://unrelated.invalid"})
        assert response.status_code == 403


def test_sessions_round_trip_computed_fields_and_recover_interrupted_build(tmp_path):
    store = Store(str(tmp_path / "db"))
    session = Session()
    session.build.status = "running"
    store.save(session)
    store.recover()
    assert store.get(session.id).build.status == "failed"


def test_store_closes_connections_when_a_transaction_finishes(tmp_path):
    store = Store(str(tmp_path / "db"))
    with store.connect() as db:
        db.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_approval_rejects_a_playback_revision_the_user_did_not_review(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "db")))
    with TestClient(app) as client:
        session = ready_session()
        session.revision = 2
        session.playback_revision = 2
        app.state.store.save(session)
        assert client.post(f"/api/sessions/{session.id}/approve", json={"revision": 1}).status_code == 409
        assert client.post(f"/api/sessions/{session.id}/approve", json={"revision": 3}).status_code == 409
        assert client.post(f"/api/sessions/{session.id}/approve", json={"revision": 2}).status_code == 200


def test_switching_server_to_live_cannot_charge_a_restored_demo_session(tmp_path):
    path = str(tmp_path / "db")
    store = Store(path)
    session = Session(mode="demo")
    store.save(session)
    app = create_app(Settings(mode="live", database_path=path))
    with TestClient(app) as client:
        response = client.post(f"/api/sessions/{session.id}/turns", json={"text": "Another idea"})
        assert response.status_code == 409
        assert "new conversation" in response.json()["detail"].lower()
