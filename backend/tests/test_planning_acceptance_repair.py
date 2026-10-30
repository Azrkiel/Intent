"""Deterministic runner/review completeness belongs inside the existing repair."""

import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.execution.verification import TRUSTED_COMMAND
from backend.app.models import LiveModels
from backend.app.planning.demo import demo_response
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session, repair_response, reviewed_framework
from backend.tests.test_models import completion


@pytest.mark.parametrize("failure", ["runner_command", "runner_placeholder", "review_coverage"])
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_acceptance_checks_share_one_content_repair(tmp_path, failure, repair_succeeds):
    session = ready_session()
    session.mode = "live"
    reviewed_framework(session)
    store = Store(str(tmp_path / "sessions.db"))
    store.save(session)
    seen = Counter()
    target = "planner:verify" if failure == "review_coverage" else "planner:phase:foundation"

    def handle(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        role = (
            "planner:verify" if "statements" in payload else
            f"planner:phase:{payload['phase']['ref']}" if "phase" in payload else
            f"planner:screen:{payload['screen']['ref']}" if "screen" in payload else "planner:outline"
        )
        seen[role] += 1
        result = demo_response(session, role, payload)
        if role.startswith("planner:phase:"):
            for package in result["packages"]:
                for task in package["tasks"]:
                    task["checks"] = [{"command": list(TRUSTED_COMMAND), "expected": "No whitespace errors"}]
        if role == target and (seen[role] == 1 or not repair_succeeds):
            if failure == "review_coverage":
                result["reviewed_statement_ids"].pop()
            elif failure == "runner_command":
                result["packages"][0]["tasks"][0]["checks"][0]["command"] = ["node", "unapproved.js"]
            else:
                result["packages"][0]["tasks"][0]["checks"][0]["expected"] = "TODO verify"
        return httpx.Response(200, json=completion(json.dumps(repair_response(body, result))))

    config = Settings(mode="live", allow_codex_execution=True)
    client = AsyncOpenAI(api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    provider = LiveModels(config, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, config).generate(session)]
        assert seen[target] == 2
        assert all(count == 1 for role, count in seen.items() if role != target)
        assert events[-1]["type"] == ("plan_ready" if repair_succeeds else "plan_error")
        current = store.get(session.id)
        assert len(current.usage) == sum(seen.values())
        assert current.planning.approval is None
        if not repair_succeeds:
            assert current.planning.active is None
    finally:
        await provider.close()


@pytest.mark.parametrize("rejection", ["rejected_statement_ids", "missing_ledger_ids"])
@pytest.mark.parametrize("incomplete", [False, True])
async def test_genuine_semantic_rejection_is_not_repaired_into_approval(tmp_path, rejection, incomplete):
    session = ready_session()
    session.mode = "live"
    reviewed_framework(session)
    store = Store(str(tmp_path / "sessions.db"))
    store.save(session)
    seen = Counter()

    def handle(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        role = (
            "planner:verify" if "statements" in payload else
            f"planner:phase:{payload['phase']['ref']}" if "phase" in payload else
            f"planner:screen:{payload['screen']['ref']}" if "screen" in payload else "planner:outline"
        )
        seen[role] += 1
        result = demo_response(session, role, payload)
        if role == "planner:verify":
            result[rejection] = (
                [next(iter(payload["statements"]))] if rejection == "rejected_statement_ids" else ["L1"]
            )
            if incomplete:
                result["reviewed_statement_ids"].pop()
        return httpx.Response(200, json=completion(json.dumps(repair_response(body, result))))

    config = Settings(mode="live")
    client = AsyncOpenAI(api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    provider = LiveModels(config, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, config).generate(session)]
        assert events[-1]["type"] == "plan_error" and seen["planner:verify"] == 1
        assert store.get(session.id).planning.active is None
    finally:
        await provider.close()
