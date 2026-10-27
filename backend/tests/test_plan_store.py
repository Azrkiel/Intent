import pytest

from backend.app.planning.contracts import OutlineProposal, PlanDocument
from backend.app.store import Store


def document():
    return PlanDocument(
        id="plan-test", revision=1, requirements_revision=2, mode="demo",
        outline=OutlineProposal(
            vision={"text": "A notes app", "ledger_ids": ["L1"]},
            journeys=[{"text": "Save and read", "ledger_ids": ["L1"]}],
            specification=[{"text": "A notes app", "ledger_ids": ["L1"]}],
            common_rules=[], choices=[], architecture="[Save] -> [Read]\n[Failure] -> [Retry]",
            screens=[], phases=[{"ref": "core", "title": "Core", "depends_on": []}],
        ), screens=[], phases=[],
    )


def test_plan_snapshots_survive_reopen_and_are_immutable(tmp_path):
    path = str(tmp_path / "state.db")
    store = Store(path)
    plan = document()
    store.save_plan("session", plan)
    store.save_plan("session", plan)
    restored = Store(path).get_plan("session", plan.id, 1)
    assert restored == plan
    assert restored.content_hash == plan.content_hash
    plan.outline.vision.text = "Changed"
    with pytest.raises(ValueError, match="immutable"):
        store.save_plan("session", plan)
    with pytest.raises(KeyError):
        store.get_plan("other-session", plan.id, 1)


def test_tampered_plan_is_not_loaded(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    store.save_plan("session", document())
    with store.connect() as db:
        db.execute("UPDATE plans SET content_hash='tampered'")
    with pytest.raises(ValueError, match="hash"):
        store.get_plan("session", "plan-test", 1)
