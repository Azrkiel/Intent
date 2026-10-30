"""Clarity v2 contract shape; no model behavior is tested here."""

import pytest
from pydantic import ValidationError

from backend.app.clarity.contracts import (
    NORTH_STAR_FIELDS,
    RUBRIC,
    ClarityState,
    DecisionProbe,
    ProbeAnswer,
    Thresholds,
)
from backend.app.domain import Candidate, Session, Turn
from backend.tests.clarity_fixtures import reading_queue_session


def test_fields_rubrics_and_thresholds_match_the_spec():
    assert NORTH_STAR_FIELDS == ("who-when", "job", "ambition", "today", "good", "fails-if")
    assert RUBRIC["who-when"] == ("W1", "W2", "W3", "W4")
    assert "O2" not in RUBRIC["good"]
    t = Thresholds()
    assert (t.alpha_pass, t.alpha_floor, t.canary_critical_recall, t.canary_overall_recall) == (
        0.80,
        0.667,
        1.0,
        0.80,
    )


def test_session_defaults_to_v1_and_v2_state_roundtrips():
    assert Session().clarity_version == 1
    session = reading_queue_session()
    session.clarity = ClarityState(revision=1, source_hash="a" * 64, mode="live")
    session.readbacks["job"] = "b" * 64
    assert Session.model_validate_json(session.model_dump_json(round_trip=True)) == session


def test_historical_session_json_without_v2_fields_still_loads():
    old = Session(id="old").model_dump(mode="json")
    for key in ("clarity_version", "clarity", "readbacks", "vetoes"):
        old.pop(key)
    assert Session.model_validate(old).clarity_version == 1


def test_suggested_and_suggestion_flags_are_omitted_when_false():
    assert "suggested" not in Turn(number=1, text="x").model_dump()
    question = Candidate(
        lens="north-star",
        question="Who uses it?",
        options=["Me", "Us"],
        code_diff="Sets proportionality.",
        divergence=3,
        uncertainty=3,
        cost_to_change=3,
    )
    assert "suggestion" not in question.model_dump()


def test_probe_answers_and_decision_probes_are_bounded():
    with pytest.raises(ValidationError):
        ProbeAnswer(probe_id="p1", choice=4)
    with pytest.raises(ValidationError):
        DecisionProbe(
            id="p",
            question="Where?",
            options=["A"],
            code_diff="x" * 20,
            context="c",
            drivers=["job"],
            kano="must-be",
            category="data-model",
        )
