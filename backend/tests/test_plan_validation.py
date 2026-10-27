import pytest

from backend.app.planning.contracts import (
    OutlineProposal,
    PhaseProposal,
    PlanDocument,
    ScreenProposal,
    SourceItem,
)
from backend.app.planning.validation import accept_outline, accept_phase, accept_screen, validate_plan
from backend.tests.planning_fixtures import outline, package, phase, ready_session, screen


def plan():
    session = ready_session()
    draft = accept_outline(OutlineProposal.model_validate(outline()), session.ledger)
    phases = [
        accept_phase(PhaseProposal.model_validate(phase()), draft, 0),
        accept_phase(
            PhaseProposal.model_validate(phase("app", [package("ui", "ui.py", ["contracts"])])), draft, 1
        ),
    ]
    doc = PlanDocument(
        id="plan",
        revision=1,
        requirements_revision=1,
        mode="demo",
        outline=draft,
        screens=[accept_screen(ScreenProposal.model_validate(screen()), draft, "notes")],
        phases=phases,
        sources=[
            SourceItem(**x.model_dump(include={"id", "type", "text", "status", "source", "turn"}))
            for x in session.ledger
        ],
    )
    return session, doc


def test_assigns_stable_ids_and_covers_confirmed_requirements():
    session, doc = plan()
    validate_plan(doc, session.ledger)
    assert doc.phases[1].packages[0].tasks[0].id == "P2-W1-T1"


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "C:/secret",
        "/etc/passwd",
        "a\\b",
        "CON.txt",
        "a.",
        "a ",
        "a:b",
        "*.py",
        "a//b",
        "a/./b",
        "nul/x",
    ],
)
def test_rejects_unsafe_owned_paths(path):
    session, doc = plan()
    doc.phases[0].packages[0].owned_paths = [path]
    with pytest.raises(ValueError):
        validate_plan(doc, session.ledger)


@pytest.mark.parametrize(
    "damage", ["citation", "coverage", "cycle", "phase", "collision", "interface", "screen"]
)
def test_blocks_invalid_plan(damage):
    session, doc = plan()
    first, second = [p.packages[0] for p in doc.phases]
    if damage == "citation":
        doc.outline.vision.ledger_ids = ["L999"]
    elif damage == "coverage":
        doc.outline.specification = doc.outline.specification[:-1]
    elif damage == "cycle":
        first.depends_on = ["ui"]
    elif damage == "phase":
        doc.phases[1].ref = "undeclared"
    elif damage == "collision":
        second.depends_on = []
        doc.outline.phases[1].depends_on = []
        second.owned_paths = ["CONTRACTS.py"]
    elif damage == "interface":
        from backend.app.planning.contracts import Interface

        second.consumes = [Interface(name="api", version="v1")]
    else:
        doc.screens[0].wireframes.pop("error")
    with pytest.raises(ValueError):
        validate_plan(doc, session.ledger)


def test_unknown_phase_and_duplicate_outline_references_rejected():
    session = ready_session()
    draft = OutlineProposal.model_validate(outline())
    draft.phases[1].ref = draft.phases[0].ref
    with pytest.raises(ValueError):
        accept_outline(draft, session.ledger)
    with pytest.raises(ValueError):
        accept_phase(
            PhaseProposal.model_validate(phase("unknown")), OutlineProposal.model_validate(outline()), 0
        )
