import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.planning_fixtures import ready_session


@pytest.fixture
def fixture(tmp_path):
    config = Settings(database_path=str(tmp_path / "sessions.db"), mode="demo")
    app = create_app(config)
    with TestClient(app) as client:
        session = ready_session()
        app.state.store.save(session)
        yield client, session, config


def post(client, session, mode="question", text="Why is this section needed?", node="intent", **changes):
    base = f"/api/sessions/{session.id}/discussion"
    target = client.get(base, params={"node_id": node}).json()["target"]
    payload = {"request_id": str(uuid4()), "target": target, "mode": mode, "text": text} | changes
    return client.post(base, json=payload), payload


def test_draft_root_has_no_fake_plan_identity_and_question_preserves_intent(fixture):
    client, session, _ = fixture
    before = client.app.state.store.get(session.id).model_dump_json(round_trip=True)
    response = client.get(f"/api/sessions/{session.id}/discussion", params={"node_id": "intent"})
    assert response.status_code == 200
    view = response.json()
    assert view["can_write"] and view["target"]["kind"] == "intent"
    assert view["target"]["plan_id"] is view["target"]["plan_hash"] is None
    response, payload = post(client, session)
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    assert message["status"] == "complete" and "DEMO" in message["reply"]["text"]
    assert client.app.state.store.get(session.id).model_dump_json(round_trip=True) == before
    assert message["request_id"] == payload["request_id"]
    assert client.get(f"/api/sessions/{session.id}/discussion").json()["messages"] == [message]


def test_direction_is_exact_scoped_turn_and_invalidates_before_inference(fixture):
    client, session, _ = fixture
    client.post(f"/api/sessions/{session.id}/plan", json={})
    identity = client.app.state.store.get(session.id).planning.active
    client.post(f"/api/sessions/{session.id}/plan/approve", json=identity.model_dump())
    seen = []
    original = client.app.state.engine.models.call

    async def observe(current, role, schema, instruction, payload):
        if role == "extractor":
            assert current.approved_revision is current.planning.approval is None
            assert current.brief is None and current.planning.status == "stale"
            seen.append(payload)
        return await original(current, role, schema, instruction, payload)

    client.app.state.engine.models.call = observe
    text = "  Use browser storage only.  "
    response, payload = post(client, session, mode="direction", text=text, node="P1")
    assert response.status_code == 200, response.text
    saved = client.app.state.store.get(session.id)
    assert saved.turns[-1].text == text
    assert saved.turns[-1].scope.model_dump() == payload["target"]
    assert seen and seen[0]["text"] == text and seen[0]["scope_context"]["selected"]["id"] == "P1"
    assert response.json()["message"]["turn_number"] == saved.turns[-1].number
    assert saved.planning.active == identity and saved.planning.approval is None
    assert saved.planning.status == "stale"
    base = f"/api/sessions/{session.id}/discussion"
    assert not client.get(base, params={"node_id": "P1"}).json()["can_write"]
    assert client.get(base, params={"node_id": "intent"}).json()["can_write"]


def test_idempotency_returns_original_without_duplicate_questions_or_turns(fixture):
    client, session, _ = fixture
    base = f"/api/sessions/{session.id}/discussion"
    first, payload = post(client, session, mode="direction", text="Use browser storage only")
    second = client.post(base, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["message"] == second.json()["message"]
    assert len(client.app.state.store.get(session.id).turns) == len(session.turns) + 1
    changed = client.post(base, json={**payload, "text": "Different direction"})
    assert changed.status_code == 409


def test_stale_or_tampered_target_and_mode_mismatch_block_without_inference(fixture):
    client, session, config = fixture
    base = f"/api/sessions/{session.id}/discussion"
    target = client.get(base).json()["target"]
    payload = {"request_id": str(uuid4()), "target": {**target, "node_hash": "0" * 64},
               "mode": "question", "text": "Explain it"}
    assert client.post(base, json=payload).status_code == 409
    payload["target"] = target
    config.mode = "live"
    assert client.post(base, json=payload).status_code == 409
    assert client.get(base).json()["messages"] == []


@pytest.mark.parametrize("citations", [["node:missing"], []])
def test_unknown_or_missing_citations_fail_without_mutating_requirements(fixture, citations):
    client, session, _ = fixture
    original = client.app.state.engine.models.call

    async def invalid(current, role, schema, instruction, payload):
        if role == "graph:question":
            return schema(text="Invented answer", citations=citations)
        return await original(current, role, schema, instruction, payload)

    client.app.state.engine.models.call = invalid
    response, _ = post(client, session)
    assert response.status_code == 200
    assert response.json()["message"]["status"] == "failed"
    assert response.json()["message"]["reply"] is None
    assert client.app.state.store.get(session.id).revision == session.revision


def test_pending_recovery_is_uncertain_and_never_replayed(fixture):
    client, session, _ = fixture
    from backend.app.discussion.contracts import DiscussionRequest

    target = client.get(f"/api/sessions/{session.id}/discussion").json()["target"]
    request = DiscussionRequest(request_id=str(uuid4()), target=target, mode="question", text="Why?")
    service = client.app.state.discussions
    message, owned = service.records.reserve(session.id, request, "Draft vision", {"selected": {}})
    assert owned and message.status == "pending"
    service.recover()
    response = client.post(f"/api/sessions/{session.id}/discussion", json=request.model_dump())
    assert response.json()["message"]["status"] == "uncertain"
    assert service.records.messages(session.id, request.target)[0].status == "uncertain"


def test_threads_are_archived_across_intent_revisions(fixture):
    client, session, _ = fixture
    post(client, session)
    post(client, session, mode="direction", text="Use browser storage only")
    view = client.get(f"/api/sessions/{session.id}/discussion", params={"node_id": "intent"}).json()
    assert view["messages"] == []
    assert len(view["history"]) == 1 and len(view["history"][0]["messages"]) == 2
    assert view["history"][0]["target"] != view["target"]
    assert view["activity"] == {}


def test_activity_is_a_revision_bound_overlay_and_marks_saved_direction(fixture):
    client, session, _ = fixture
    client.post(f"/api/sessions/{session.id}/plan", json={})
    before = client.app.state.store.get(session.id).planning.active
    post(client, session, node="P1")
    view = client.get(f"/api/sessions/{session.id}/discussion", params={"node_id": "root"}).json()
    assert view["activity"] == {"P1": {"messages": 1, "pending_direction": False}}
    post(client, session, node="P1", mode="direction", text="Use browser storage only")
    view = client.get(f"/api/sessions/{session.id}/discussion", params={"node_id": "P1"}).json()
    assert view["activity"] == {"P1": {"messages": 2, "pending_direction": True}}
    current = client.app.state.store.get(session.id)
    assert current.planning.active == before and current.planning.approval is None


def test_context_excludes_sibling_task_bodies_and_is_bounded(fixture):
    client, session, _ = fixture
    client.post(f"/api/sessions/{session.id}/plan", json={})
    seen = []
    original = client.app.state.engine.models.call

    async def observe(current, role, schema, instruction, payload):
        if role == "graph:question":
            seen.append(payload)
        return await original(current, role, schema, instruction, payload)

    client.app.state.engine.models.call = observe
    response, _ = post(client, session, node="P2-W1")
    assert response.json()["message"]["status"] == "complete"
    assert seen[0]["selected"]["id"] == "P2-W1"
    assert [node["id"] for node in seen[0]["ancestors"]] == ["root", "P2"]
    assert '"P2-W2"' not in json.dumps(seen[0]["selected"]["body"])


def test_empty_and_oversized_text_rejected(fixture):
    client, session, _ = fixture
    for text in ["   ", "x" * 6001]:
        response, _ = post(client, session, text=text)
        assert response.status_code == 422


def test_direction_failure_keeps_exact_source_and_execution_invalidation(fixture):
    from backend.app.models import ModelError

    client, session, _ = fixture
    invalidated = []

    async def invalidate(session_id):
        invalidated.append(session_id)

    async def fail(current, role, schema, instruction, payload):
        assert invalidated == [session.id]
        assert current.approved_revision is None and current.brief is None
        raise ModelError("Synthetic extraction failure")

    client.app.state.executor.invalidate = invalidate
    client.app.state.engine.models.call = fail
    text = "  Keep my exact new vision.  "
    response, _ = post(client, session, mode="direction", text=text)
    assert response.json()["message"]["status"] == "failed"
    current = client.app.state.store.get(session.id)
    assert current.turns[-1].text == text and current.turns[-1].scope is not None
    assert current.approved_revision is None and current.analysis_complete is False


def test_every_graph_node_kind_has_a_bound_discussion(fixture):
    client, session, _ = fixture
    client.post(f"/api/sessions/{session.id}/plan", json={})
    plan = client.get(f"/api/sessions/{session.id}/plan").json()
    nodes = plan["graph"]["nodes"]
    assert {node["kind"] for node in nodes} == {"root", "phase", "package", "task", "screen"}
    for kind in {node["kind"] for node in nodes}:
        node = next(node for node in nodes if node["kind"] == kind)
        response, _ = post(client, session, node=node["id"])
        assert response.json()["message"]["status"] == "complete", kind


@pytest.mark.parametrize("partial", [False, True], ids=["complete", "partial"])
@pytest.mark.parametrize("per_session,global_limit", [(2, 2), (1, 1)])
def test_discussion_source_and_ancestors_match_displayed_worker_limits(
    tmp_path, partial, per_session, global_limit
):
    from backend.app.models import ModelError
    from backend.app.planning.contracts import content_hash

    config = Settings(
        database_path=str(tmp_path / "sessions.db"), mode="demo",
        codex_max_workers=per_session, codex_global_max_workers=global_limit,
    )
    app = create_app(config)
    with TestClient(app) as client:
        session = ready_session()
        app.state.store.save(session)
        original = app.state.engine.models.call

        async def accepted_outline_only(current, role, schema, instruction, payload):
            if partial and role.startswith("planner:screen:"):
                raise ModelError("Synthetic interruption after the accepted outline")
            return await original(current, role, schema, instruction, payload)

        app.state.engine.models.call = accepted_outline_only
        client.post(f"/api/sessions/{session.id}/plan", json={})
        detail = client.get(f"/api/sessions/{session.id}/plan").json()
        assert detail["partial"] is partial
        graph = detail["graph"]
        root = next(node for node in graph["nodes"] if node["id"] == "root")
        expected = {"per_session": per_session, "global": global_limit}
        assert root["body"]["orchestration"]["worker_limits"] == expected
        view = client.get(f"/api/sessions/{session.id}/discussion").json()
        assert view["target"]["node_hash"] == content_hash(root["body"])
        assert view["target"]["plan_hash"] == graph["source"]["content_hash"]
        saved = app.state.store.get(session.id)
        _, _, _, _, context = app.state.discussions.resolve(saved, "P1")
        assert context["ancestors"][0]["body"]["orchestration"]["worker_limits"] == expected


def test_questions_preserve_existing_plan_and_requirements_approval(fixture):
    client, session, _ = fixture
    client.post(f"/api/sessions/{session.id}/plan", json={})
    identity = client.app.state.store.get(session.id).planning.active
    client.post(f"/api/sessions/{session.id}/plan/approve", json=identity.model_dump())
    before = client.app.state.store.get(session.id)
    response, _ = post(client, session, node="P1")
    assert response.json()["message"]["status"] == "complete"
    saved = client.app.state.store.get(session.id)
    assert saved.planning.active == saved.planning.approval == identity
    assert saved.approved_revision == session.revision
    assert saved.turns == before.turns and saved.ledger == before.ledger


def test_budget_failure_retains_durable_failure_without_constructing_a_provider(fixture):
    from backend.app.models import LiveModels

    client, session, config = fixture
    config.mode = session.mode = "live"
    config.session_budget_usd = 0.000001
    client.app.state.store.save(session)
    provider = LiveModels(config)
    client.app.state.engine.models = provider
    response, _ = post(client, session)
    assert response.status_code == 200
    assert response.json()["message"]["status"] == "failed"
    assert "budget" in response.json()["message"]["error"].lower()
    assert provider.client is None and client.app.state.store.get(session.id).usage == []


def test_stale_reply_preserves_fresh_requirements_and_billed_usage(fixture):
    from backend.app.domain import Usage

    client, session, _ = fixture

    async def changed(current, role, schema, instruction, payload):
        current.usage.append(Usage(
            role=role, model="synthetic", input_tokens=1, output_tokens=1,
            estimated_usd=0.01, latency_ms=1,
        ))
        fresh = client.app.state.store.get(current.id)
        fresh.revision += 1
        fresh.approved_revision = None
        client.app.state.store.save(fresh)
        return schema(text="Old answer", citations=["node:intent"])

    client.app.state.engine.models.call = changed
    response, _ = post(client, session)
    assert response.json()["message"]["status"] == "failed"
    saved = client.app.state.store.get(session.id)
    assert saved.revision == session.revision + 1 and saved.approved_revision is None
    assert len(saved.usage) == 1


def test_oversized_context_rejected_before_reservation_or_model(fixture):
    from backend.app.domain import LedgerItem

    client, session, _ = fixture
    session.ledger.extend(LedgerItem(
        id=f"EXTRA-{index}", type="feature", text="Large context", status="inferred",
        source="x" * 6000, turn=1,
    ) for index in range(50))
    client.app.state.store.save(session)
    response, _ = post(client, session)
    assert response.status_code == 409 and "byte limit" in response.json()["detail"]
    assert client.get(f"/api/sessions/{session.id}/discussion").json()["messages"] == []


@pytest.mark.asyncio
async def test_concurrent_posts_do_not_repeat_model_calls_or_requests(tmp_path):
    import asyncio

    import httpx

    app = create_app(Settings(database_path=str(tmp_path / "sessions.db"), mode="demo"))
    session = ready_session()
    app.state.store.save(session)
    target = app.state.discussions.view(session)["target"]
    payload = {"request_id": str(uuid4()), "target": target, "mode": "question", "text": "Why?"}
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    original = app.state.engine.models.call

    async def delayed(current, role, schema, instruction, context):
        calls.append(role)
        entered.set()
        await release.wait()
        return await original(current, role, schema, instruction, context)

    app.state.engine.models.call = delayed
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = asyncio.create_task(client.post(f"/api/sessions/{session.id}/discussion", json=payload))
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(client.post(f"/api/sessions/{session.id}/discussion", json=payload))
        release.set()
        results = await asyncio.gather(first, second)
    assert all(response.status_code == 200 for response in results)
    assert results[0].json()["message"] == results[1].json()["message"]
    assert calls == ["graph:question"]
