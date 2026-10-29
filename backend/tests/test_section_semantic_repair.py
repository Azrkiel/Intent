"""Every generated section shares schema and deterministic checks in one repair."""

import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.models import LiveModels
from backend.app.planning.demo import demo_response
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session
from backend.tests.test_models import completion


@pytest.mark.parametrize("failure", [
    "screen_states", "screen_citation", "phase_exclusions", "phase_path",
    "phase_dependency", "phase_interface", "phase_citation", "final_coverage",
    "screen_schema_then_semantic", "phase_schema_then_semantic",
])
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_section_errors_share_one_repair_and_keep_prior_sections(tmp_path, failure, repair_succeeds):
    session = ready_session()
    session.mode = "live"
    original_sources = session.model_dump(mode="json")["ledger"]
    config = Settings(mode="live", database_path=str(tmp_path / "sessions.db"))
    store = Store(config.database_path)
    store.save(session)
    target = (
        "planner:screen:main" if failure.startswith("screen") else
        "planner:phase:implementation" if failure == "final_coverage" else "planner:phase:foundation"
    )
    seen = Counter()
    requests = []

    def handle(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        role = (
            f"planner:phase:{payload['phase']['ref']}" if "phase" in payload else
            f"planner:screen:{payload['screen']['ref']}" if "screen" in payload else
            "planner:verify" if "statements" in payload else "planner:outline"
        )
        requests.append(body)
        seen[role] += 1
        result = demo_response(session, role, payload)
        if failure == "final_coverage" and role == "planner:phase:foundation":
            for package in result["packages"]:
                for claim in package["acceptance"]:
                    claim["status"] = "proposal"
        if role == target:
            if failure.endswith("schema_then_semantic") and seen[role] == 1:
                return httpx.Response(200, json=completion("invalid JSON"))
            corrupt = seen[role] == 1 or not repair_succeeds or failure.endswith("schema_then_semantic")
            if corrupt:
                if failure in {"screen_states", "screen_schema_then_semantic"}:
                    result["wireframes"].pop("empty")
                elif failure == "screen_citation":
                    result["purpose"]["ledger_ids"] = ["UNKNOWN"]
                elif failure in {"phase_exclusions", "phase_schema_then_semantic"}:
                    result["packages"][0]["exclusions"] = []
                elif failure == "phase_path":
                    result["packages"][0]["owned_paths"] = ["../escape"]
                elif failure == "phase_dependency":
                    result["packages"][0]["depends_on"] = ["unknown"]
                elif failure == "phase_interface":
                    result["packages"][0]["consumes"] = [{"name": "unknown", "version": "v1"}]
                elif failure == "phase_citation":
                    result["goal"]["ledger_ids"] = ["UNKNOWN"]
                else:
                    for package in result["packages"]:
                        for claim in package["acceptance"]:
                            claim["status"] = "proposal"
        return httpx.Response(200, json=completion(json.dumps(result)))

    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(config, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, config).generate(session)]
    finally:
        await provider.close()
    success = repair_succeeds and not failure.endswith("schema_then_semantic")
    assert seen[target] == 2
    assert len(session.usage) == len(requests)
    assert all(count == 1 for role, count in seen.items() if role != target)
    assert events[-1]["type"] == ("plan_ready" if success else "plan_error")
    assert len(session.planning.attempts) == 1
    attempt = session.planning.attempts[0]
    assert attempt.passes.count(target) == 1
    assert session.planning.approval is None
    assert session.model_dump(mode="json")["ledger"] == original_sources
    restored = store.get(session.id)
    assert restored.usage == session.usage
    if not success:
        assert "after one repair" in attempt.error
        assert session.planning.active is None and attempt.outline is not None
        assert len(attempt.screens) == (0 if failure.startswith("screen") else 1)
        assert len(attempt.phases) == (1 if failure == "final_coverage" else 0)
