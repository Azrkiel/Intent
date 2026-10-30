"""Provenance is computed by the application; these tests make no model calls."""

import pytest

from backend.app.clarity.contracts import ClaimMapDraft, NotApplicable, ScenarioDraft, ScenarioDrafts
from backend.app.clarity.provenance import aspect_gaps, build_claims, build_scenarios, tiling_gaps
from backend.tests.clarity_fixtures import draft, reading_queue_session

L6_PART = "Reject blank titles and non-https URLs inline"


def claims_for(*drafts):
    session = reading_queue_session()
    claims, problems = build_claims(ClaimMapDraft(claims=list(drafts)), session.ledger)
    return session, claims, problems


def test_exact_quote_from_a_confirmed_item_confirms_a_stated_claim():
    _, claims, problems = claims_for(draft(L6_PART, ["failure-recovery/validation"], spans=[("L6", L6_PART)]))
    assert (claims[0].id, claims[0].status, problems) == ("C1", "confirmed", [])


def test_misquote_or_unknown_item_cannot_confirm():
    _, claims, problems = claims_for(
        draft("Reject empty titles", ["failure-recovery/validation"], spans=[("L6", "Reject empty titles")]),
        draft("Sync", ["data/storage"], spans=[("L99", "Sync")]),
    )
    assert [c.status for c in claims] == ["proposal", "proposal"]
    assert any("quotes text not in L6" in p for p in problems)
    assert any("unknown requirement L99" in p for p in problems)


@pytest.mark.parametrize(
    "finding, text, tags, spans, word",
    [
        (
            "structure.2",
            "Depends on localStorage with plain JSON and no frameworks",
            ["structure/dependencies"],
            [("L4", "localStorage"), ("L11", "Use reversible technical defaults.")],
            "json",
        ),
        (
            "data.1",
            "Store a JSON array under key readingQueue in localStorage",
            ["data/storage"],
            [("L4", "localStorage")],
            "readingqueue",
        ),
        (
            "journeys.1",
            "Swipe or delete to remove an item immediately",
            ["journeys/actions"],
            [("L5", "delete immediately")],
            "swipe",
        ),
        (
            "failure-recovery.0",
            f"{L6_PART} and disable the Add button",
            ["failure-recovery/validation"],
            [("L6", L6_PART)],
            "disable",
        ),
        (
            "structure.0",
            "Show unread articles newest first, then read articles",
            ["structure/components"],
            [("L3", "show the unread article newest first")],
            "read",
        ),
        (
            "purpose.0",
            "A personal reading queue with no accounts or sync",
            ["purpose/problem"],
            [("L1", "Build my reading queue")],
            "sync",
        ),
        (
            "failure-recovery.2",
            "Clear corrupt storage and wait for confirmation",
            ["failure-recovery/recovery"],
            [("L8", "If stored JSON is corrupt offer Reset and wait for my click")],
            "clear",
        ),
    ],
)
def test_novelty_tripwire_downgrades_each_human_review_addition(finding, text, tags, spans, word):
    _, claims, problems = claims_for(draft(text, tags, spans=spans))
    assert claims[0].status == "proposal", finding
    assert word in claims[0].flags[0], finding
    assert any("states words its quote does not support" in p for p in problems)


def test_quote_tiling_names_the_dropped_duplicate_rule():
    session, claims, _ = claims_for(draft(L6_PART, ["failure-recovery/validation"], spans=[("L6", L6_PART)]))
    assert tiling_gaps(claims, session.ledger)["L6"] == ["allow", "duplicates"]


def test_delegation_cannot_cover_costly_choices_and_proposals_must_serve_the_north_star():
    _, _, problems = claims_for(
        draft(
            "Use IndexedDB",
            ["data/storage"],
            basis="delegated",
            serves="good",
            reversibility=3,
            spans=[("L11", "Use reversible technical defaults.")],
        ),
        draft("Add cloud sync between devices", ["scope/included"], basis="proposed"),
    )
    assert any("costly to reverse" in p for p in problems)
    assert any("serves no North Star field" in p for p in problems)


def test_entailed_claims_need_confirmed_premises():
    _, claims, problems = claims_for(
        draft(L6_PART, ["failure-recovery/validation"], spans=[("L6", L6_PART)]),
        draft(
            "Nothing is saved for a rejected entry",
            ["failure-recovery/validation"],
            basis="entailed",
            premises=["C1"],
            derivation="Rejection happens before saving.",
        ),
        draft(
            "Rejected entries are logged",
            ["failure-recovery/validation"],
            basis="entailed",
            premises=["C9"],
            derivation="Missing premise.",
        ),
    )
    assert [c.status for c in claims] == ["confirmed", "derived", "proposal"]
    assert any("C3 needs existing premises" in p for p in problems)


def test_exclusion_needs_a_confirmed_grounding():
    _, claims, _ = claims_for(
        draft("No server or sync", ["scope/excluded"], basis="excluded", spans=[("L9", "No server, sync")])
    )
    assert claims[0].status == "excluded"


def test_aspects_need_a_claim_or_a_cited_not_applicable_entry():
    session, claims, _ = claims_for(draft(L6_PART, ["failure-recovery/validation"], spans=[("L6", L6_PART)]))
    gaps = aspect_gaps(
        claims,
        [
            NotApplicable(tag="access/permissions", reason="Single user", ledger_ids=["L2"]),
            NotApplicable(tag="access/actors", reason="Unsupported", ledger_ids=["L99"]),
        ],
        session.ledger,
    )
    assert "failure-recovery/validation" not in gaps
    assert "access/permissions" not in gaps
    assert "access/actors" in gaps


def test_unknown_tags_are_problems():
    _, _, problems = claims_for(draft(L6_PART, ["failure-recovery/typing"], spans=[("L6", L6_PART)]))
    assert any("unknown tag failure-recovery/typing" in p for p in problems)


def test_scenarios_must_exercise_behavior_and_exclusions():
    _, claims, _ = claims_for(
        draft(L6_PART, ["failure-recovery/validation"], spans=[("L6", L6_PART)]),
        draft("No server or sync", ["scope/excluded"], basis="excluded", spans=[("L9", "No server, sync")]),
    )
    scenarios, problems = build_scenarios(
        ScenarioDrafts(
            scenarios=[
                ScenarioDraft(
                    title="Blank title",
                    given="the form is empty",
                    when="I click Add",
                    then="an inline error shows",
                    claims=["C1", "C7"],
                    kind="failure",
                )
            ]
        ),
        claims,
    )
    assert scenarios[0].id == "S1"
    assert any("unknown claim C7" in p for p in problems)
    assert any("No exclusion scenario shows C2" in p for p in problems)
    assert any("at least one journey scenario" in p for p in problems)
