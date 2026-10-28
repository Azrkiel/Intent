import json

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.domain import Delta, Session
from backend.app.models import LiveModels, ModelError
from backend.app.settings import Settings


def completion(content):
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 1,
        "model": "nano",
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }


async def test_live_model_repairs_json_once_and_tracks_both_calls():
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion("not json" if len(requests) == 1 else '{"add": []}'))

    client = AsyncOpenAI(
        api_key="test",
        base_url="https://test.invalid/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(Settings(send_thinking_controls=False), client=client)
    session = Session()
    result = await provider.call(session, "extractor", Delta, "Extract evidence.", {"text": "hello"})
    assert result.add == []
    assert len(requests) == 2
    assert "validation" in requests[1]["messages"][-1]["content"].lower()
    assert len(session.usage) == 2
    assert requests[0]["model"] == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    assert "chat_template_kwargs" not in requests[0]
    assert "reasoning_budget" not in requests[0]
    await client.close()


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_unconvertible_planning_diagram_uses_only_the_existing_repair(repair_succeeds):
    from backend.app.planning.contracts import OutlineProposal
    from backend.tests.planning_fixtures import outline

    requests = []
    valid = outline()
    invalid = {**valid, "architecture": "[Input] -> [\u4fdd\u5b58]"}

    def handle(request):
        requests.append(json.loads(request.content))
        payload = valid if repair_succeeds and len(requests) == 2 else invalid
        return httpx.Response(200, json=completion(json.dumps(payload)))

    client = AsyncOpenAI(
        api_key="offline-test",
        base_url="https://test.invalid/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(Settings(), client=client)
    session = Session()
    try:
        if repair_succeeds:
            result = await provider.call(session, "planner:outline", OutlineProposal, "Plan the fixture.", {})
            assert result.architecture.isascii()
        else:
            with pytest.raises(ModelError, match="after one repair"):
                await provider.call(session, "planner:outline", OutlineProposal, "Plan the fixture.", {})
        assert len(requests) == 2
        assert "architecture" in requests[1]["messages"][-1]["content"]
        assert len(session.usage) == 2
    finally:
        await provider.close()


async def test_live_model_never_silently_uses_demo_after_two_invalid_outputs():
    client = AsyncOpenAI(
        api_key="test",
        base_url="https://test.invalid/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=completion("bad")))
        ),
    )
    session = Session()
    with pytest.raises(ModelError, match="valid JSON"):
        await LiveModels(Settings(), client=client).call(session, "extractor", Delta, "Extract.", {})
    assert len(session.usage) == 2
    assert sum(item.input_tokens for item in session.usage) == 40
    assert sum(item.output_tokens for item in session.usage) == 20
    await client.close()


async def test_live_budget_rejects_calls_before_request():
    provider = LiveModels(Settings(session_budget_usd=0.000001))
    with pytest.raises(ModelError, match="budget"):
        await provider.call(Session(), "compiler", Delta, "Compile.", {})


@pytest.mark.parametrize(
    "role,enabled,budget",
    [
        ("extractor", False, None),
        ("critic:contradictions", True, 2048),
        ("compiler", True, 6144),
    ],
)
async def test_requested_thinking_controls_are_sent(role, enabled, budget):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"add": []}'))

    client = AsyncOpenAI(
        api_key="test",
        base_url="https://test.invalid/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(Settings(send_thinking_controls=True), client=client)
    try:
        await provider.call(Session(), role, Delta, "Return the test JSON contract.", {})
        body = requests[0]
        assert body["chat_template_kwargs"] == {"enable_thinking": enabled}
        if budget is None:
            assert "reasoning_budget" not in body
        else:
            assert body["reasoning_budget"] == budget
    finally:
        await client.close()
