"""Offline framework/gate checks; these do not establish model quality."""

import pytest

from backend.app.domain import LedgerItem, Session, Turn, gate_for
from backend.tests.test_ledger import ready_session


def test_vague_six_slot_live_session_cannot_be_build_ready():
    session = ready_session()
    session.mode = "live"
    assert not gate_for(session).ready
    assert gate_for(session).percent < 100
    assert any("framework" in text.lower() for text in gate_for(session).blockers)


def mapped_session():
    from backend.app.framework import (
        ASPECTS,
        FrameworkAssessment,
        FrameworkMap,
        FrameworkReview,
        entry_catalog,
        source_hash,
    )

    session = ready_session()
    session.mode = "live"
    session.revision = session.extracted_revision = 1
    text = "Create a habit, check it off, and reload to see today's completion."
    session.turns = [Turn(number=1, text=text)]
    framework = FrameworkMap.model_validate({
        "sections": [
            {
                "area": area,
                "entries": [
                    {
                        "aspect": aspect,
                        "text": f"{aspect}: {text}",
                        "ledger_ids": [item.id for item in session.ledger],
                        "status": "confirmed" if area == "purpose" else "proposal",
                    }
                    for aspect in aspects
                ],
            }
            for area, aspects in ASPECTS.items()
        ],
        "questions": [],
    })
    session.framework_review = FrameworkReview(
        revision=session.revision,
        source_hash=source_hash(session),
        mode="live",
        framework=framework,
        assessment=FrameworkAssessment(
            reviewed_entry_ids=list(entry_catalog(framework)),
            reviewed_areas=list(ASPECTS),
        ),
    )
    return session


def test_complete_current_independently_reviewed_map_can_pass_and_roundtrip():
    session = mapped_session()
    assert gate_for(session).ready
    assert Session.model_validate_json(session.model_dump_json(round_trip=True)) == session


@pytest.mark.parametrize("change", ["revision", "ledger", "mode", "missing-review", "partial-review"])
def test_stale_or_incomplete_framework_never_passes(change):
    session = mapped_session()
    if change == "revision":
        session.revision += 1
    elif change == "ledger":
        session.ledger[0].text = "Replace habits with a shared approval workflow"
    elif change == "mode":
        session.framework_review.mode = "demo"
    elif change == "missing-review":
        session.framework_review.assessment = None
    else:
        session.framework_review.assessment.reviewed_entry_ids.pop()
    assert not gate_for(session).ready


@pytest.mark.parametrize("defect", ["area", "aspect", "coverage", "citation", "confirmation"])
def test_structural_omissions_and_invalid_evidence_block_even_with_accepting_reviewer(defect):
    from backend.app.framework import entry_catalog

    session = mapped_session()
    framework = session.framework_review.framework
    if defect == "area":
        framework.sections.pop()
    elif defect == "aspect":
        framework.sections[1].entries.pop()
    elif defect == "coverage":
        for section in framework.sections:
            for entry in section.entries:
                entry.ledger_ids = ["L1"]
    elif defect == "citation":
        framework.sections[0].entries[0].ledger_ids = ["L999"]
    else:
        session.ledger.append(LedgerItem(id="L7", type="assumption", text="Use accounts", turn=1))
        framework.sections[0].entries[0].ledger_ids.append("L7")
        from backend.app.framework import source_hash

        session.framework_review.source_hash = source_hash(session)
    session.framework_review.assessment.reviewed_entry_ids = list(entry_catalog(framework))
    assert not gate_for(session).ready


def test_critical_framework_questions_block_independently_of_candidate_ranking():
    from backend.app.framework import FrameworkQuestion

    session = mapped_session()
    session.framework_review.framework.questions = [FrameworkQuestion(
        area="data",
        question="Should completing a habit save across devices?",
        options=["Keep it in this browser", "Sync between signed-in devices"],
        code_diff="Browser storage adapter versus server persistence and account-scoped sync routes",
        targets=["L3"],
    )]
    session.candidates = []
    assert not gate_for(session).ready
    assert any("across devices" in text for text in gate_for(session).blockers)


def test_semantic_review_can_reject_a_structurally_complete_but_vague_map():
    from backend.app.framework import FrameworkIssue

    session = mapped_session()
    session.framework_review.assessment.issues = [FrameworkIssue(
        area="journeys", detail="The action sequence has no concrete saved result or recovery path."
    )]
    assert not gate_for(session).ready
    assert any("saved result" in text for text in gate_for(session).blockers)


@pytest.mark.parametrize("condition", [
    "complete", "map-fails", "review-fails", "partial-review", "vague", "missing-data", "critical"
])
async def test_engine_maps_reviews_and_keeps_failures_or_critical_gaps_closed(tmp_path, condition):
    from backend.app.demo import DemoModels
    from backend.app.engine import Engine
    from backend.app.framework import FrameworkIssue, FrameworkQuestion
    from backend.app.models import ModelError
    from backend.app.store import Store

    template = mapped_session().framework_review
    session = mapped_session()
    session.framework_review = None
    calls = []

    class Models(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            calls.append((role, payload))
            if role.startswith("critic:"):
                return schema(candidates=[])
            if role == "framework:map":
                if condition == "map-fails":
                    raise ModelError("Framework provider timed out")
                result = template.framework.model_copy(deep=True)
                if condition == "missing-data":
                    result.sections = [section for section in result.sections if section.area != "data"]
                return result
            if role == "framework:review":
                if condition == "review-fails":
                    raise ModelError("Independent reviewer timed out")
                result = template.assessment.model_copy(deep=True)
                if condition == "partial-review":
                    result.reviewed_entry_ids.pop()
                if condition == "vague":
                    result.issues = [FrameworkIssue(
                        area="journeys", detail="Actions have no concrete result."
                    )]
                if condition == "critical":
                    result.questions = [FrameworkQuestion(
                        area="data", question="Where must the completion survive a reload?",
                        options=["In this browser", "On a shared server"],
                        code_diff="A local browser persistence adapter versus server write and read routes",
                        targets=["L3"],
                    )]
                return result
            return await super().call(session, role, schema, instruction, payload)

    store = Store(str(tmp_path / "sessions.db"))
    events = [event async for event in Engine(store, Models()).analyze(session)]
    restored = store.get(session.id)
    assert gate_for(restored).ready is (condition == "complete")
    assert any(role == "framework:map" for role, _ in calls)
    assert events[-1]["session"]["gate"]["ready"] is (condition == "complete")
    if condition == "complete":
        review_payload = next(payload for role, payload in calls if role == "framework:review")
        assert review_payload["entry_catalog"]
        assert review_payload["turns"][0]["text"] == session.turns[0].text
    if condition == "critical":
        assert restored.current_question.targets == ["L3"]
        assert "survive a reload" in restored.current_question.question


async def test_new_utterance_invalidates_framework_before_extraction(tmp_path):
    from backend.app.demo import DemoModels
    from backend.app.engine import Engine
    from backend.app.models import ModelError
    from backend.app.store import Store

    class FailedExtraction(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            raise ModelError("Extraction failed")

    session = mapped_session()
    session.approved_revision = session.revision
    stream = Engine(Store(str(tmp_path / "db")), FailedExtraction()).turn(session, "Change the users")
    first = await anext(stream)
    assert first["session"]["framework_review"] is None
    assert first["session"]["gate"]["ready"] is False
    assert first["session"]["approved_revision"] is None
    await stream.aclose()


def test_framework_proposals_survive_in_brief_without_becoming_confirmed_requirements():
    from backend.app.domain import Brief, trace_brief

    session = mapped_session()
    brief = trace_brief(session, Brief())
    assert "Framework proposal" in brief.markdown
    assert "components:" in brief.markdown
    assert all(item.type == "decision" for item in session.ledger)


@pytest.mark.parametrize("action", ["approve", "compile", "build", "plan"])
def test_legacy_live_approval_cannot_bypass_the_new_gate(tmp_path, action):
    from fastapi.testclient import TestClient

    from backend.app.domain import Brief, Playback
    from backend.app.main import create_app
    from backend.app.settings import Settings

    app = create_app(Settings(mode="live", database_path=str(tmp_path / "db")))
    session = mapped_session()
    session.framework_review = None
    session.approved_revision = session.playback_revision = session.revision
    session.playback = Playback(sentences=["An older approved summary."])
    session.brief = Brief()
    app.state.store.save(session)
    with TestClient(app) as client:
        payload = {} if action == "plan" else {"revision": session.revision}
        response = client.post(f"/api/sessions/{session.id}/{action}", json=payload)
        assert response.status_code == 409


async def test_map_defects_receive_one_bounded_repair_without_asking_user_to_design_it(tmp_path):
    from backend.app.demo import DemoModels
    from backend.app.engine import Engine
    from backend.app.framework import FrameworkIssue
    from backend.app.store import Store

    session = mapped_session()
    template = session.framework_review
    calls, feedback = [], []

    class Models(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            calls.append(role)
            if role.startswith("critic:"):
                return schema(candidates=[])
            if role == "framework:map":
                feedback.append(payload.get("review_feedback"))
                return template.framework.model_copy(deep=True)
            if role == "framework:review":
                result = template.assessment.model_copy(deep=True)
                if calls.count(role) == 1:
                    result.issues = [FrameworkIssue(area="structure", detail="Name the storage interface.")]
                return result
            return await super().call(session, role, schema, instruction, payload)

    events = [event async for event in Engine(Store(str(tmp_path / "db")), Models()).analyze(session)]
    assert events[-1]["session"]["gate"]["ready"]
    assert calls.count("framework:map") == calls.count("framework:review") == 2
    assert feedback[0] is None
    assert feedback[1]["issues"][0]["detail"] == "Name the storage interface."


async def test_reanalysis_requires_fresh_playback_approval_and_brief(tmp_path):
    from backend.app.demo import DemoModels
    from backend.app.domain import Brief, Build, Playback
    from backend.app.engine import Engine
    from backend.app.store import Store

    session = mapped_session()
    session.approved_revision = session.playback_revision = session.revision
    session.playback = Playback(sentences=["Old approved summary."])
    session.brief = Brief()
    session.build = Build(status="complete")
    events = [event async for event in Engine(Store(str(tmp_path / "db")), DemoModels()).analyze(session)]
    assert events[-1]["session"]["approved_revision"] is None
    assert session.playback_revision is None and session.brief is None
    assert session.build.status == "idle"


def test_large_reviewed_map_does_not_consume_requirement_line_allowance():
    from backend.app.domain import Brief, trace_brief
    from backend.app.framework import entry_catalog

    session = mapped_session()
    for section in session.framework_review.framework.sections:
        section.entries.extend(
            section.entries[0].model_copy(deep=True) for _ in range(20 - len(section.entries))
        )
    session.framework_review.assessment.reviewed_entry_ids = list(
        entry_catalog(session.framework_review.framework)
    )
    brief = trace_brief(session, Brief())
    assert len(brief.lines) == len(session.ledger)
    assert len(brief.framework_lines) == 160
