import pytest

from backend.app.domain import (
    Brief,
    BriefLine,
    Candidate,
    Delta,
    LedgerItem,
    Session,
    Turn,
    apply_delta,
    gate_for,
    rank_candidates,
    trace_brief,
)


def session_with_words(text="A habit tracker, no login, saved across my phone and laptop"):
    return Session(id="test", turns=[Turn(number=1, text=text)])


def test_confirmed_requires_quote_from_actual_user_turn():
    session = session_with_words()
    delta = Delta.model_validate(
        {
            "add": [
                {"type": "goal", "text": "Habit tracker", "status": "confirmed", "source": "A habit tracker"},
                {"type": "feature", "text": "AI coaching", "status": "confirmed", "source": "AI coaching"},
                {"type": "constraint", "text": "Fast", "status": "confirmed", "source": None},
            ]
        }
    )
    apply_delta(session, delta, 1)
    assert session.ledger[0].status == "confirmed"
    assert [x.status for x in session.ledger[1:]] == ["inferred", "inferred"]
    assert [x.id for x in session.ledger] == ["L1", "L2", "L3"]


def test_update_cannot_confirm_using_a_quote_from_a_different_turn():
    session = session_with_words()
    session.ledger = [LedgerItem(id="L1", type="goal", text="Tracker", status="inferred", turn=1)]
    session.turns.append(Turn(number=2, text="Yes"))
    apply_delta(
        session,
        Delta.model_validate({"update": [{"id": "L1", "status": "confirmed", "source": "A habit tracker"}]}),
        2,
    )
    assert session.ledger[0].status == "inferred"


def test_updates_preserve_ids_and_unknown_ids_are_rejected_atomically():
    session = session_with_words()
    with pytest.raises(ValueError, match="Unknown ledger"):
        apply_delta(
            session,
            Delta.model_validate(
                {
                    "add": [{"type": "goal", "text": "Tracker", "status": "inferred"}],
                    "update": [{"id": "L99", "status": "open"}],
                }
            ),
            1,
        )
    assert session.ledger == []


def candidate(**kwargs):
    return Candidate(
        id="Q1",
        lens="data",
        targets=["L1"],
        question="Where should data live?",
        options=["This device", "Cloud sync"],
        code_diff="localStorage vs API routes and a projects table",
        **kwargs,
    )


def test_rank_uses_product_drops_cosmetic_questions_and_deduplicates():
    high = candidate(divergence=3, uncertainty=3, cost_to_change=3)
    low = candidate(divergence=1, uncertainty=3, cost_to_change=3)
    assert rank_candidates([low, high, high])[0].impact == 27
    assert len(rank_candidates([low, high, high])) == 1


def test_equal_impact_prioritizes_contradictions_independent_of_completion_order():
    other = candidate(divergence=3, uncertainty=3, cost_to_change=3)
    contradiction = other.model_copy(
        update={"id": "Q2", "lens": "contradictions", "question": "How can these requirements coexist?"}
    )
    assert rank_candidates([other, contradiction])[0].id == "Q2"
    assert rank_candidates([contradiction, other])[0].id == "Q2"


def ready_session():
    session = Session(id="ready", analysis_complete=True)
    for index, slot in enumerate(["goal", "core-flow", "data", "access", "non-goals", "success-criterion"]):
        session.ledger.append(
            LedgerItem(
                id=f"L{index + 1}",
                type="decision",
                slot=slot,
                text=slot,
                status="confirmed",
                source=slot,
                turn=1,
            )
        )
    return session


def test_gate_requires_slots_completed_analysis_and_no_high_impact_or_conflicts():
    session = ready_session()
    assert gate_for(session).ready
    session.candidates = [candidate(divergence=3, uncertainty=2, cost_to_change=2)]
    assert not gate_for(session).ready
    session.candidates = []
    session.analysis_complete = False
    assert not gate_for(session).ready
    session.analysis_complete = True
    session.ledger[0].status = "conflict"
    assert not gate_for(session).ready


def test_traceability_deletes_invalid_citations_and_covers_every_confirmed_item():
    session = ready_session()
    brief = Brief(
        lines=[
            BriefLine(section="Goal", text="Build it", ledger_ids=["L1"]),
            BriefLine(section="Features", text="Invented billing", ledger_ids=["L999"]),
        ]
    )
    checked = trace_brief(session, brief, rejected=[0])
    assert all("billing" not in x.text for x in checked.lines)
    ids = {id for line in checked.lines for id in line.ledger_ids}
    assert ids == {x.id for x in session.ledger}
    assert "[L1]" in checked.markdown


def test_inferred_items_cannot_become_requirements_in_compiled_brief():
    session = ready_session()
    session.ledger.append(LedgerItem(id="L7", type="assumption", text="Stripe billing", turn=1))
    brief = trace_brief(
        session, Brief(lines=[BriefLine(section="Must have", text="Add Stripe", ledger_ids=["L7"])])
    )
    assert not any(x.text == "Add Stripe" for x in brief.lines)
    assert any("Undecided" in x.section and "L7" in x.ledger_ids for x in brief.lines)
