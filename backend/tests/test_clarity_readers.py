"""G4 reader variation: the two readers must not be byte-identical calls."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from backend.app.clarity.contracts import Answers
from backend.app.demo import DemoModels
from backend.app.domain import Session, gate_for
from backend.app.engine import Engine
from backend.app.main import create_app
from backend.app.models import LiveModels
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.clarity_fixtures import reading_queue_session
from backend.tests.test_clarity_api import client_with, run_clarity

MODES = ["perspective", "temperature", "tier"]


class Recorder(DemoModels):
    def __init__(self):
        self.reader_calls = {}

    async def call(self, session, role, schema, instruction, payload):
        if role.startswith("clarity:reader:"):
            self.reader_calls[role] = (instruction, payload)
        return await super().call(session, role, schema, instruction, payload)


async def readers(mode, tmp_path):
    models = Recorder()
    engine = Engine(Store(str(tmp_path / "db")), models)
    session = reading_queue_session()
    session.clarity_reader_variation = mode
    [event async for event in engine.analyze(session)]
    return models.reader_calls, session


async def test_perspective_mode_gives_reader_b_a_different_instruction_same_payload(tmp_path):
    calls, _ = await readers("perspective", tmp_path)
    (ia, pa), (ib, pb) = calls["clarity:reader:a"], calls["clarity:reader:b"]
    assert ia != ib and "skeptical" in ib
    assert pa == pb


@pytest.mark.parametrize("mode", ["temperature", "tier"])
async def test_other_modes_route_reader_b_by_role(tmp_path, mode):
    calls, session = await readers(mode, tmp_path)
    assert set(calls) == {"clarity:reader:a", f"clarity:reader:b:{mode}"}
    assert calls["clarity:reader:a"][0] == calls[f"clarity:reader:b:{mode}"][0]
    assert all(f.reader_b for f in session.clarity.fields if f.text)


@pytest.mark.parametrize("mode", MODES)
async def test_demo_stays_scripted_and_labeled_in_every_mode(tmp_path, mode):
    _, session = await readers(mode, tmp_path)
    assert session.clarity.mode == session.mode
    assert all(f.failing == ["G3"] for f in session.clarity.fields)
    assert not gate_for(session).ready


def test_session_default_comes_from_settings(tmp_path):
    for configured in MODES:
        config = Settings(
            mode="demo", clarity_reader_variation=configured, database_path=str(tmp_path / configured)
        )
        app = create_app(config)
        with TestClient(app) as client:
            assert client.post("/api/sessions", json={}).json()["clarity_reader_variation"] == configured
    app = create_app(Settings(mode="demo", database_path=str(tmp_path / "d")))
    with TestClient(app) as client:
        assert client.post("/api/sessions", json={}).json()["clarity_reader_variation"] == "perspective"
        made = client.post("/api/sessions", json={"clarity_reader_variation": "tier"}).json()
        assert made["clarity_reader_variation"] == "tier"
        assert client.post("/api/sessions", json={"clarity_reader_variation": "bogus"}).status_code == 422


def test_endpoint_updates_mode_and_invalidates_the_readout(tmp_path):
    session = reading_queue_session()
    app = client_with(tmp_path, session)
    app.state.engine.models = DemoModels()
    with TestClient(app) as client:
        before = run_clarity(client, session.id)
        assert before["clarity"] and before["clarity_readout"]
        url = f"/api/sessions/{session.id}/clarity/reader-variation"
        same = client.post(url, json={"mode": "perspective", "revision": before["revision"]}).json()
        assert same["clarity"] is not None
        data = client.post(url, json={"mode": "tier", "revision": before["revision"]}).json()
        assert data["clarity_reader_variation"] == "tier"
        assert data["clarity"] is None and data["analysis_complete"] is False
        assert not data["gate"]["ready"]
        assert client.get(f"/api/sessions/{session.id}").json()["clarity_reader_variation"] == "tier"
        again = client.post(f"/api/sessions/{session.id}/analyze").json()
        assert again["clarity"]["fields"]
        assert client.post(url, json={"mode": "bogus", "revision": 1}).status_code == 422
        assert client.post(url, json={"mode": "tier", "revision": 999}).status_code == 409


def test_endpoint_refuses_v1_sessions(tmp_path):
    with TestClient(create_app(Settings(mode="demo", database_path=str(tmp_path / "db")))) as client:
        made = client.post("/api/sessions", json={}).json()
        r = client.post(
            f"/api/sessions/{made['id']}/clarity/reader-variation", json={"mode": "tier", "revision": 0}
        )
        assert r.status_code == 409


async def live_request(role):
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        body = {
            "id": "t", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"answers": []}'},
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        return httpx.Response(200, json=body)

    client = AsyncOpenAI(
        api_key="t", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = LiveModels(Settings(), client=client)
    session = Session()
    await provider.call(session, role, Answers, "Read.", {"fields": []})
    await client.close()
    return seen[0], session.usage[0]


async def test_live_routing_per_reader_role():
    a, usage_a = await live_request("clarity:reader:a")
    b, _ = await live_request("clarity:reader:b")
    warm, _ = await live_request("clarity:reader:b:temperature")
    tier, usage_tier = await live_request("clarity:reader:b:tier")
    s = Settings()
    assert (a["temperature"], a["model"]) == (0.2, s.nano_model)
    assert (b["temperature"], b["model"]) == (0.2, s.nano_model)
    assert warm["temperature"] == 0.8 and warm["model"] == s.nano_model
    assert tier["temperature"] == 0.2 and tier["model"] == s.super_model
    assert usage_tier.model == s.super_model
