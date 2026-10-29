import pytest
from pydantic import ValidationError

from backend.app.domain import Session
from backend.app.planning.contracts import (
    LeafTaskProposal,
    OutlineProposal,
    PhaseProposal,
    ScreenProposal,
    Statement,
)


def test_old_sessions_default_to_unapproved_planning():
    session = Session.model_validate({"id": "old"})
    assert session.planning.status == "draft"
    assert session.planning.approval is None
    assert session.planning.attempts == []


def test_provider_cannot_set_application_identity_or_approval():
    with pytest.raises(ValidationError):
        Statement(text="Build it", ledger_ids=["L1"], id="trusted")
    with pytest.raises(ValidationError):
        OutlineProposal(approved=True)


@pytest.mark.parametrize("text", ["", "   "])
def test_statements_reject_empty_text(text):
    with pytest.raises(ValidationError):
        Statement(text=text, ledger_ids=["L1"])


def test_leaf_requires_steps_acceptance_and_verification():
    with pytest.raises(ValidationError):
        LeafTaskProposal(title="Make it", steps=[], acceptance=[], checks=[])


@pytest.mark.parametrize("section", ["outline", "screen", "phase"])
def test_descriptions_preserve_unicode_in_the_provider_schema(section):
    from backend.tests.planning_fixtures import outline, phase, screen

    if section == "outline":
        schema, data = OutlineProposal, outline()
        data["architecture"] = "[Input] \u2192 [Save]"
    elif section == "screen":
        schema, data = ScreenProposal, screen()
        data["wireframes"]["empty"] = "[Input] \u2192 [Save]"
    else:
        schema, data = PhaseProposal, phase()
        data["flow"] = "[Input] \u2192 [Save]"
    assert schema.model_validate(data).model_dump() == data


@pytest.mark.parametrize("value", ["\x00", "text\x1b", "x" * 12001, "\ud800", "   "])
def test_descriptions_reject_controls_invalid_unicode_and_excess_size(value):
    from backend.tests.planning_fixtures import outline

    with pytest.raises(ValidationError):
        OutlineProposal.model_validate({**outline(), "architecture": value})


def test_user_facing_statements_still_allow_unicode():
    statement = Statement(text="\u4fdd\u5b58\u7b14\u8bb0", ledger_ids=["L1"])
    assert statement.text == "\u4fdd\u5b58\u7b14\u8bb0"
