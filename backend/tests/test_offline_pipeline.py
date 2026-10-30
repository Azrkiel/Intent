"""Exercise the live adapter over fake HTTP; these tests measure no model quality."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from backend.app import prompts
from backend.app.demo import DemoModels
from backend.app.domain import LENSES, Session, Turn
from backend.app.main import create_app
from backend.app.models import LiveModels
from backend.app.settings import Settings
from backend.tests.test_api import send
from backend.tests.test_models import completion


@pytest.fixture
def offline_live(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        mode="live",
        # The mock handler maps only v1 schema titles, so this stays the v1 HTTP-contract check.
        clarity_version=1,
        NEBIUS_API_KEY="offline-test-only",
        database_path=str(tmp_path / "sessions.db"),
        build_root=str(tmp_path / "builds"),
    )
    requests, failures = [], {}

    async def handle(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        title = json.loads(system.rsplit("\n", 1)[-1])["title"]
        role = {
            "Delta": "extractor",
            "Ranking": "ranker",
            "Playback": "playback",
            "Brief": "compiler",
            "Verification": "verifier",
            "FrameworkMap": "framework:map",
            "FrameworkAssessment": "framework:review",
        }.get(title)
        if title == "Critique":
            role = next(f"critic:{lens}" for lens in LENSES if system.startswith(prompts.critic_prompt(lens)))
        assert role, title
        requests.append((role, body["model"]))
        if failures.get(role, 0):
            failures[role] -= 1
            return httpx.Response(200, json=completion("invalid JSON"))
        payload = json.loads(body["messages"][1]["content"])
        session = Session(
            mode="live",
            ledger=payload.get("ledger", []),
            questions=payload.get("already_asked", []),
            current_question=payload.get("active_question"),
            turns=[
                Turn(number=n, text=payload.get("text", "")) for n in range(1, payload.get("turn", 1) + 1)
            ],
        )
        result = await DemoModels().call(session, role, None, "", payload)
        return httpx.Response(200, json=completion(result.model_dump_json(round_trip=True)))

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    sdk = AsyncOpenAI(
        api_key="offline-test-only", base_url="https://offline.invalid/v1", http_client=transport
    )
    provider = LiveModels(settings, client=sdk)
    monkeypatch.setattr("backend.app.main.LiveModels", lambda config: provider)
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app, settings, requests, failures
    assert sdk.is_closed()


def ready_interview(client):
    state = client.post("/api/sessions", json={}).json()
    state = send(
        client,
        state["id"],
        "I want a habit tracker, no login, saved across my phone and laptop, "
        "and reminders should be automatic.",
    )
    for _ in range(10):
        if state["gate"]["ready"]:
            return state
        state = send(client, state["id"], state["current_question"]["options"][0])
    pytest.fail("Scripted interview did not become ready")


def approve(client, state):
    base = f"/api/sessions/{state['id']}"
    assert client.post(base + "/playback").status_code == 200
    assert client.post(base + "/approve", json={"revision": state["revision"]}).status_code == 200
    return base


def test_http_contract_pipeline_compiles_tracks_usage_restores_and_invalidates(offline_live):
    client, app, settings, requests, _ = offline_live
    state = ready_interview(client)
    base = approve(client, state)
    response = client.post(base + "/compile")
    assert response.status_code == 200, response.text
    compiled = response.json()
    assert compiled["mode"] == "live"
    assert [(call["role"], call["model"]) for call in compiled["usage"][-2:]] == [
        ("compiler", settings.ultra_model),
        ("verifier", settings.super_model),
    ]
    assert len(compiled["usage"]) == len(requests)
    assert compiled["estimated_usd"] > 0  # Fake token counts, never an actual charge.
    covered = {id for line in compiled["brief"]["lines"] for id in line["ledger_ids"]}
    assert covered == {item["id"] for item in compiled["ledger"] if item["status"] == "confirmed"}
    for item in compiled["ledger"]:
        assert item["source"] in compiled["turns"][item["turn"] - 1]["text"]
    assert "No accounts or payments" in client.get(base + "/brief").text
    count = len(requests)
    assert client.post(base + "/compile").json()["brief"] == compiled["brief"]
    assert len(requests) == count
    # Read back via the real SQLite store, not the in-memory session.
    restored = app.state.store.get(state["id"])
    assert restored.brief.markdown == compiled["brief"]["markdown"]
    assert len(restored.usage) == len(requests)
    assert client.post(base + "/build").status_code == 409
    changed = send(client, state["id"], "Actually, this device only for now")
    assert changed["mode"] == "live"
    assert changed["approved_revision"] is None
    assert changed["playback_revision"] is None
    assert changed["brief"] is None
    assert changed["build"]["status"] == "idle"
    assert client.get(base + "/brief").status_code == 404
    assert client.get(base + "/preview").status_code == 404
    assert client.post(base + "/compile").status_code == 409
    original_data_ids = {item["id"] for item in compiled["ledger"] if item["slot"] == "data"}
    assert all(
        item["text"] == "Keep data on this device only"
        for item in changed["ledger"]
        if item["id"] in original_data_ids
    )


# The extractor asks afresh once, so it needs four bad replies to fail the turn.
@pytest.mark.parametrize("role,attempts", [("extractor", 4), ("critic:edges", 2)])
def test_invalid_json_closes_gate_retains_both_attempts_and_retries(offline_live, role, attempts):
    client, _, _, requests, failures = offline_live
    state = client.post("/api/sessions", json={}).json()
    base = f"/api/sessions/{state['id']}"
    failures[role] = attempts
    response = client.post(base + "/turns", json={"text": "I want a habit tracker, no login"})
    assert response.status_code == 200
    state = client.get(base).json()
    assert state["mode"] == "live"
    assert not state["analysis_complete"]
    assert not state["gate"]["ready"]
    assert state["warnings"]
    assert len([item for item in state["usage"] if item["role"] == role]) == attempts
    assert len(state["usage"]) == len(requests)
    assert client.post(base + "/compile").status_code == 409
    retry = client.post(base + "/analyze")
    assert retry.status_code == 200, retry.text
    assert retry.json()["analysis_complete"]
    assert retry.json()["mode"] == "live"
    assert retry.json()["extracted_revision"] == retry.json()["revision"]
    assert retry.json()["ledger"]


@pytest.mark.parametrize("role", ["compiler", "verifier"])
def test_invalid_compilation_never_exposes_a_partial_brief(offline_live, role):
    client, _, _, requests, failures = offline_live
    state = ready_interview(client)
    base = approve(client, state)
    failures[role] = 2
    response = client.post(base + "/compile")
    assert response.status_code == 502
    saved = client.get(base).json()
    assert saved["mode"] == "live"
    assert saved["brief"] is None
    assert len([item for item in saved["usage"] if item["role"] == role]) == 2
    assert len(saved["usage"]) == len(requests)
    assert client.get(base + "/brief").status_code == 404
    assert client.post(base + "/build").status_code == 409
