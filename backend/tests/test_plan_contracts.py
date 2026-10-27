import pytest
from pydantic import ValidationError

from backend.app.domain import Session
from backend.app.planning.contracts import (
    LeafTaskProposal,
    OutlineProposal,
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
