import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.planning_fixtures import ready_session
from backend.tests.test_planning_api import generate


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "sessions.db"), mode="demo"))
    with TestClient(app) as browser:
        session = ready_session()
        app.state.store.save(session)
        yield browser, session


def test_plan_detail_binds_complete_graph_identity_and_stale_state(client):
    browser, session = client
    detail = generate(browser, session)
    graph = detail["graph"]
    assert graph["source"]["content_hash"] == detail["plan"]["content_hash"]
    assert graph["source"]["requirements_revision"] == detail["requirements_revision"]
    assert graph["partial"] is False
    assert graph["state"] == "review_ready"
    browser.post(f"/api/sessions/{session.id}/turns", json={"text": "Use browser storage only"})
    updated = browser.get(f"/api/sessions/{session.id}/plan").json()
    assert updated["graph"]["state"] == "stale"
    assert updated["graph"]["source"]["content_hash"] == graph["source"]["content_hash"]


def test_plan_detail_without_accepted_outline_has_no_fabricated_graph(client):
    browser, session = client
    assert browser.get(f"/api/sessions/{session.id}/plan").json()["graph"] is None
