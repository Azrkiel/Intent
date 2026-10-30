"""Decision register rules; no model calls."""

from collections import Counter

import pytest

from backend.app.clarity.contracts import (
    Claim,
    Decision,
    DecisionProbe,
    ProbeAnswer,
    Scenario,
    Thresholds,
)
from backend.app.clarity.decisions import (
    attach_confirmations,
    build,
    decision_problems,
    quality,
    resolve_vetoes,
    split,
    wasted_questions,
)
from backend.app.domain import AskedQuestion, Candidate, LedgerItem, Session


def probe(category="behavior", kano="performance", due=None, pid="p1"):
    return DecisionProbe(
        id=pid,
        question="What happens to duplicates?",
        options=["Allow", "Merge", "Reject"],
        code_diff="Insert path versus a lookup-and-merge path",
        context="Adding a URL twice (C2)",
        drivers=["good"],
        kano=kano,
        category=category,
        claims=["C2"],
        due_phase=due,
    )


def answers(*choices, pid="p1"):
    return [[ProbeAnswer(probe_id=pid, choice=c)] for c in choices]


def test_split_is_zero_for_agreement_and_one_for_an_even_split():
    assert split([0, 0, 0, 0]) == 0
    assert split([0, 0, 1, 1]) == pytest.approx(1.0)
    assert split([0, 0, 0, 1]) == pytest.approx(0.811, abs=0.001)


def test_agreement_produces_no_decision():
    assert build([probe()], answers(1, 1, 1, 1), Counter(), Thresholds()) == []


def test_one_way_doors_are_always_asked():
    [d] = build([probe(category="data-model")], answers(0, 0, 0, 1), Counter(), Thresholds())
    assert (d.reversibility, d.status) == ("one-way", "open")


def test_three_of_four_two_way_agreement_becomes_a_vetoable_default():
    [d] = build([probe(kano="must-be")], answers(0, 0, 0, 1), Counter(), Thresholds())
    assert (d.status, d.owner, d.outcome) == ("delegated", "delegated", "Allow")
    assert "good" in d.because


def test_must_be_split_is_asked_and_delighter_is_defaulted():
    [must] = build([probe(kano="must-be")], answers(0, 0, 1, 1), Counter(), Thresholds())
    [nice] = build([probe(kano="delighter")], answers(0, 0, 1, 1), Counter(), Thresholds())
    assert must.status == "open" and nice.status == "delegated"


def test_deferred_decisions_keep_their_phase_and_low_scores_stop_asking():
    [later] = build([probe(due="P2")], answers(0, 0, 1, 2), Counter(), Thresholds())
    assert (later.status, later.due_phase) == ("deferred", "P2")
    [stopped] = build([probe()], answers(0, 0, 1, 1), Counter({"behavior": 2}), Thresholds())
    assert stopped.status == "delegated" and stopped.score < Thresholds().decision_stop


def test_quality_is_the_weakest_link_and_problems_name_it():
    [d] = build([probe(kano="must-be")], answers(0, 0, 0, 1), Counter(), Thresholds())
    claims = [
        Claim(
            id="C2",
            text="Allow duplicates",
            tags=["failure-recovery/validation"],
            basis="stated",
            status="confirmed",
        )
    ]
    attach_confirmations([d], [])
    d.quality = quality(d, claims, [])
    assert d.quality["commitment"] is False
    assert any("commitment" in p for p in decision_problems([d]))
    scenarios = [
        Scenario(
            id="S1",
            title="Duplicate",
            given="a saved URL",
            when="I add it again",
            then="both entries show",
            claims=["C2"],
            kind="journey",
        )
    ]
    attach_confirmations([d], scenarios)
    d.quality = quality(d, claims, scenarios)
    assert all(d.quality.values()) and decision_problems([d]) == []


def test_open_decisions_block():
    [d] = build([probe(category="identity")], answers(0, 1, 0, 1), Counter(), Thresholds())
    assert decision_problems([d]) == ["Decide: What happens to duplicates?"]


def test_vetoed_decision_is_open_until_the_user_answers():
    veto = Decision(
        id="V1",
        status="open",
        question="What happens to duplicates?",
        options=["Allow", "Merge"],
        code_diff="Insert versus merge",
        context="c",
        drivers=["good"],
        kano="performance",
        category="behavior",
        reversibility="two-way",
        votes=[0, 0, 0, 1],
    )
    assert resolve_vetoes([veto], [])[0].status == "open"
    asked = AskedQuestion(
        question=Candidate(
            id="V1",
            lens="decision",
            question=veto.question,
            options=veto.options,
            code_diff="Insert versus merge",
            divergence=3,
            uncertainty=2,
            cost_to_change=2,
        ),
        answer="Merge",
        turn=3,
    )
    resolved = resolve_vetoes([veto], [asked])[0]
    assert (resolved.status, resolved.owner, resolved.outcome) == ("decided", "user", "Merge")


def test_wasted_questions_count_answers_that_changed_no_requirement():
    session = Session(ledger=[LedgerItem(id="L1", type="goal", text="x", turn=2)])
    question = Candidate(
        lens="decision",
        question="Which one?",
        options=["A", "B"],
        code_diff="Different code paths",
        divergence=3,
        uncertainty=2,
        cost_to_change=2,
    )
    session.questions = [
        AskedQuestion(question=question, answer="A", turn=2),
        AskedQuestion(question=question, answer="B", turn=3),
    ]
    assert wasted_questions(session) == (1, 2)
