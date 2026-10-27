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
    provider = LiveModels(Settings(), client=client)
    session = Session()
    result = await provider.call(session, "extractor", Delta, "Extract evidence.", {"text": "hello"})
    assert result.add == []
    assert len(requests) == 2
    assert "validation" in requests[1]["messages"][-1]["content"].lower()
    assert len(session.usage) == 2
    assert requests[0]["model"] == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    await client.close()


async def test_live_model_never_silently_uses_demo_after_two_invalid_outputs():
    client = AsyncOpenAI(
        api_key="test",
        base_url="https://test.invalid/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=completion("bad")))
        ),
    )
    with pytest.raises(ModelError, match="valid JSON"):
        await LiveModels(Settings(), client=client).call(Session(), "extractor", Delta, "Extract.", {})
    await client.close()


async def test_live_budget_rejects_calls_before_request():
    provider = LiveModels(Settings(session_budget_usd=0.000001))
    with pytest.raises(ModelError, match="budget"):
        await provider.call(Session(), "compiler", Delta, "Compile.", {})
