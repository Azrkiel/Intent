"""Deterministic outline failures share the existing schema repair allowance."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.domain import LedgerItem
from backend.app.models import LiveModels
from backend.app.planning.demo import demo_response
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session, repair_response
from backend.tests.test_models import completion


@pytest.mark.parametrize("failure", ["common_rules", "specification", "choices", "citation", "dependency"])
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_outline_semantics_receive_one_repair_with_preserved_usage(tmp_path, failure, repair_succeeds):
    session = ready_session()
    session.mode = "live"
    session.ledger.append(LedgerItem(
        id="L7", type="decision", text="An unresolved design choice", status="open", turn=1,
    ))
    store = Store(str(tmp_path / "sessions.db"))
    store.save(session)
    requests = []
    remaining_roles = iter([
        "planner:screen:main", "planner:phase:foundation", "planner:phase:implementation", "planner:verify",
    ])

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        payload = json.loads(body["messages"][1]["content"])
        role = "planner:outline" if len(requests) <= 2 else next(remaining_roles)
        result = demo_response(session, role, payload)
        if len(requests) == 1 or (len(requests) == 2 and not repair_succeeds):
            if failure == "common_rules":
                result["common_rules"] = []
            elif failure == "specification":
                result["specification"] = []
            elif failure == "choices":
                result["choices"] = []
            elif failure == "citation":
                result["vision"]["ledger_ids"] = ["UNKNOWN"]
            else:
                result["phases"][0]["depends_on"] = ["implementation"]
        return httpx.Response(200, json=completion(json.dumps(repair_response(body, result))))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    config = Settings(mode="live")
    provider = LiveModels(config, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, config).generate(session)]
    finally:
        await provider.close()
    expected_count = 6 if repair_succeeds else 2
    assert len(requests) == expected_count
    assert len(store.get(session.id).usage) == expected_count
    assert len(session.planning.attempts) == 1
    assert session.planning.attempts[0].passes.count("planner:outline") == 1
    assert session.planning.approval is None
    assert events[-1]["type"] == ("plan_ready" if repair_succeeds else "plan_error")
    repair_prompt = requests[1]["messages"][-1]["content"]
    assert "Validation:" in repair_prompt
    if failure == "common_rules":
        assert "Common rules miss constraints or exclusions" in repair_prompt
    if not repair_succeeds:
        assert session.planning.active is None and session.planning.attempts[0].outline is None


async def test_schema_error_then_semantic_error_does_not_get_a_third_response(tmp_path):
    session = ready_session()
    session.mode = "live"
    store = Store(str(tmp_path / "sessions.db"))
    store.save(session)
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, json=completion("invalid JSON"))
        result = demo_response(session, "planner:outline", {})
        result["common_rules"] = []
        return httpx.Response(200, json=completion(json.dumps(repair_response(requests[-1], result))))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    config = Settings(mode="live")
    provider = LiveModels(config, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, config).generate(session)]
    finally:
        await provider.close()
    assert events[-1]["type"] == "plan_error"
    assert len(requests) == len(session.usage) == 2
    assert "after one repair" in session.planning.attempts[0].error
    assert session.planning.active is session.planning.approval is None
