import pytest

from backend.app.execution.contracts import Run
from backend.app.execution.store import ExecutionStore
from backend.app.store import Store


def run(session_id="session"):
    return Run(
        session_id=session_id,
        package_id="P1-W1",
        plan={"plan_id": "plan", "revision": 1, "requirements_revision": 1, "content_hash": "a" * 64},
    )


def test_claims_are_durable_unique_and_recovery_never_duplicates_dispatch(tmp_path):
    store = ExecutionStore(Store(str(tmp_path / "state.db")))
    first = store.claim(run())
    with pytest.raises(ValueError):
        store.claim(run())
    with pytest.raises(ValueError):
        store.claim(run("other"))
    store.patch(first.id, lambda current: setattr(current, "dispatch_intent", "turn/start"))
    reopened = ExecutionStore(Store(str(tmp_path / "state.db")))
    reopened.recover()
    restored = reopened.get(first.id)
    assert restored.status == "blocked" and restored.dispatch_intent == "turn/start"
    assert restored.error
    assert len(reopened.list("session")) == 1


def test_patch_merges_decisions_without_losing_cancel_request(tmp_path):
    store = ExecutionStore(Store(str(tmp_path / "state.db")))
    record = store.claim(run())
    store.patch(record.id, lambda current: setattr(current, "cancel_requested", True))
    store.patch(record.id, lambda current: current.logs.append("Synthetic report"))
    assert store.get(record.id).cancel_requested
