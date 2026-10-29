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
