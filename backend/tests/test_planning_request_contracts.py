"""Offline provider regressions for accepted section identities and runner inputs."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.demo import DemoModels
from backend.app.execution.verification import POLICY, TRUSTED_COMMAND
from backend.app.models import LiveModels
from backend.app.planning.demo import demo_response
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session, repair_response, reviewed_framework
from backend.tests.test_models import completion


@pytest.mark.parametrize("section", ["screen", "phase"])
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_wrong_section_reference_uses_existing_repair_before_acceptance(
    tmp_path, section, repair_succeeds
):
    session = ready_session()
    session.mode = "live"
    store = Store(str(tmp_path / "sessions.db"))
    reviewed_framework(session)
    store.save(session)
    target = f"planner:{section}:{'main' if section == 'screen' else 'foundation'}"
    requests = []
    target_requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        payload = json.loads(body["messages"][1]["content"])
        if "statements" in payload:
            role = "planner:verify"
        elif "phase" in payload:
            role = f"planner:phase:{payload['phase']['ref']}"
        elif "screen" in payload:
            role = f"planner:screen:{payload['screen']['ref']}"
        else:
            role = "planner:outline"
        result = demo_response(session, role, payload)
        if role == target:
            target_requests.append(body)
            if len(target_requests) == 1 or not repair_succeeds:
                result["ref"] += "-changed"
        return httpx.Response(200, json=completion(json.dumps(repair_response(body, result))))

    client = AsyncOpenAI(
        api_key="offline-test",
        base_url="https://test.invalid/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    settings = Settings(mode="live")
    provider = LiveModels(settings, client=client)
    try:
        events = [event async for event in PlanningService(store, provider, settings).generate(session)]
        assert len(target_requests) == 2
        assert "ref" in target_requests[1]["messages"][-1]["content"]
        retained = store.get(session.id)
        attempt = retained.planning.attempts[0]
        assert len(retained.planning.attempts) == 1
        assert attempt.passes.count(target) == 1
        assert len(retained.usage) == len(requests)
        assert len([usage for usage in retained.usage if usage.role == target]) == 2
        assert retained.planning.approval is None
        assert provider.reserved[session.id] == 0
        if repair_succeeds:
            assert events[-1]["type"] == "plan_ready"
            assert [phase.ref for phase in attempt.phases] == ["foundation", "implementation"]
            assert [screen.ref for screen in attempt.screens] == ["main"]
        else:
            assert events[-1]["type"] == "plan_error"
            assert "after one repair" in events[-1]["message"]
            assert retained.planning.active is None
            assert attempt.phases == []
            assert len(attempt.screens) == (1 if section == "phase" else 0)
            assert "planner:verify" not in attempt.passes
    finally:
        await provider.close()


@pytest.mark.parametrize("execution_enabled", [True, False])
async def test_phase_requests_receive_current_execution_capabilities_only_when_enabled(
    tmp_path, execution_enabled
):
    session = ready_session()
    store = Store(str(tmp_path / "sessions.db"))
    store.save(session)
    phase_payloads = []

    class Capture(DemoModels):
        async def call(self, current, role, schema, instruction, payload):
            if role.startswith("planner:phase:"):
                phase_payloads.append(payload)
            return await super().call(current, role, schema, instruction, payload)

    settings = Settings(allow_codex_execution=execution_enabled)
    events = [event async for event in PlanningService(store, Capture(), settings).generate(session)]
    assert events[-1]["type"] == "plan_ready"
    assert len(phase_payloads) == 2
    for payload in phase_payloads:
        policy = payload.get("execution_policy")
        if execution_enabled:
            assert policy["name"] == POLICY
            assert policy["allowed_commands"] == [TRUSTED_COMMAND]
            assert policy["behavioral_tests_supported"] is False
        else:
            assert policy is None
