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


async def test_invalid_critic_output_names_the_wrong_lens_and_unknown_targets(tmp_path):
    # Live v2 runs only reported "invalid targets or the wrong lens", which cannot be diagnosed.
    class StrayCritic(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "critic:edges":
                question = dict(
                    question="Which empty state comes first?", options=["Show a hint", "Show nothing"],
                    code_diff="Render an onboarding hint versus a blank list",
                    divergence=3, uncertainty=2, cost_to_change=3,
                )
                return schema(candidates=[
                    Candidate(lens="data", targets=[session.ledger[0].id], **question),
                    Candidate(lens="edges", targets=["L99"], **question),
                ])
            return await super().call(session, role, schema, instruction, payload)

    store = Store(str(tmp_path / "sessions.db"))
    session = ready_session()
    store.save(session)
    async for _ in Engine(store, StrayCritic()).analyze(session):
        pass
    warning = next(w for w in store.get(session.id).warnings if "edges" in w)
    assert "lens data" in warning and "L99" in warning


async def test_a_critic_with_invalid_targets_gets_one_corrective_retry(tmp_path):
    # Live critics put code_diff's file paths in targets; one slip closed the whole pass.
    class SlipsOnce(DemoModels):
        calls = 0
        feedback = None

        async def call(self, session, role, schema, instruction, payload):
            if role == "critic:edges":
                self.calls += 1
                if self.calls == 1:
                    return schema(candidates=[Candidate(
                        lens="edges", targets=["src/db/schema.sql"],
                        question="Which empty state comes first?",
                        options=["Show a hint", "Show nothing"],
                        code_diff="Render an onboarding hint versus a blank list",
                        divergence=3, uncertainty=2, cost_to_change=3,
                    )])
                self.feedback = payload.get("review_feedback")
            return await super().call(session, role, schema, instruction, payload)

    store = Store(str(tmp_path / "sessions.db"))
    session = ready_session()
    store.save(session)
    models = SlipsOnce()
    async for _ in Engine(store, models).analyze(session):
        pass
    assert models.calls == 2 and "src/db/schema.sql" in models.feedback
    assert not any("edges" in warning for warning in store.get(session.id).warnings)


@pytest.mark.parametrize("ranking_fails", [False, True])
async def test_ranker_can_check_settled_answers_without_bypassing_failures(tmp_path, ranking_fails):
    class ContextAware(DemoModels):
        received_context = False

        async def call(self, session, role, schema, instruction, payload):
            if role.startswith("critic:"):
                candidates = []
                if role == "critic:identity":
                    candidates = [
                        Candidate(
                            lens="identity",
                            targets=[session.ledger[0].id],
                            question="Should this already confirmed decision be changed?",
                            options=["Keep the confirmed decision", "Choose a different decision"],
                            code_diff="Keep the approved access guard versus replacing its policy",
                            divergence=3,
                            uncertainty=2,
                            cost_to_change=3,
                        )
                    ]
                return schema(candidates=candidates)
            if role == "ranker":
                self.received_context = (
                    payload.get("ledger") == [item.model_dump() for item in session.ledger]
                    and payload.get("already_asked") == []
                    and "active_question" in payload
                )
                if ranking_fails:
                    raise ModelError("Synthetic ranking failure")
                return schema(
                    scores=[
                        {
                            "id": payload["candidates"][0]["id"],
                            "divergence": 1 if self.received_context else 3,
                            "uncertainty": 2,
                            "cost_to_change": 3,
                        }
                    ]
                )
            return await super().call(session, role, schema, instruction, payload)

    store = Store(str(tmp_path / "sessions.db"))
    session = ready_session()
    provider = ContextAware()
    async for _ in Engine(store, provider).analyze(session):
        pass
    assert provider.received_context
    assert public_session(session)["gate"]["ready"] is (not ranking_fails)
    assert session.analysis_complete is (not ranking_fails)


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
