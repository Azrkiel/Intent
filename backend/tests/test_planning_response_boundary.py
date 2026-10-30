"""Provider-boundary robustness; all HTTP responses here are synthetic."""

import hashlib
import io
import json
import zipfile

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.domain import Session
from backend.app.execution.verification import TRUSTED_COMMAND
from backend.app.models import LiveModels, ModelError
from backend.app.planning.context import preflight_checks
from backend.app.planning.contracts import OutlineProposal, PhaseProposal, ScreenProposal
from backend.app.planning.demo import demo_response
from backend.app.planning.export import export_bundle
from backend.app.planning.graph import project_graph
from backend.app.planning.render import render_engineering, render_human
from backend.app.planning.service import PlanningService
from backend.app.planning.validation import validate_plan
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import outline, phase, ready_session, reviewed_framework, screen
from backend.tests.test_models import completion


def provider_for(handle):
    client = AsyncOpenAI(
        api_key="offline-test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    return LiveModels(Settings(mode="live"), client=client)


@pytest.mark.parametrize("section", ["outline", "screen", "phase", "package"])
async def test_unicode_descriptions_are_preserved_without_spending_a_repair(section):
    glyphs = (
        "\u250c\u2500Input\u2500\u2510\n\u2502 Save \u2192 Read \u2190 Retry \u2502\n"
        "\u2514\u2500\u2534\u2500\u2518\nFail \u2193 Error"
    )
    if section == "outline":
        schema, data, role = OutlineProposal, outline(), "planner:outline"
        data["architecture"] = glyphs
        data["vision"]["text"] = "Keep \u2192 and \u201cquotes\u201d in prose: \u4fdd\u5b58"
    elif section == "screen":
        schema, data, role = ScreenProposal, screen(), "planner:screen:notes"
        data["wireframes"]["empty"] = glyphs
    else:
        schema, data, role = PhaseProposal, phase(), "planner:phase:core"
        if section == "phase":
            data["flow"] = glyphs
        else:
            data["packages"][0]["flow"] = glyphs
        data["packages"][0]["tasks"][0]["steps"][0] = "Keep \u2192 in product instructions"
    expected = glyphs
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion(json.dumps(data)))

    provider = provider_for(handle)
    session = Session()
    try:
        result = (await provider.call(session, role, schema, "Plan the fixture.", {})).model_dump()
        if section == "outline":
            assert result["architecture"] == expected
            assert result["vision"] == data["vision"]
            assert result["phases"] == data["phases"]
        elif section == "screen":
            assert result["wireframes"]["empty"] == expected
            assert result["purpose"] == data["purpose"]
        else:
            assert (result["flow"] if section == "phase" else result["packages"][0]["flow"]) == expected
            assert result["packages"][0]["tasks"] == data["packages"][0]["tasks"]
            assert result["ref"] == data["ref"]
        assert len(requests) == len(session.usage) == 1
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "bad_value", ["[Input]\x00 -> [Read]", "[Input]\x1b -> [Read]", "\u2192" * 12001],
    ids=["nul-control", "escape-control", "size-limit"],
)
async def test_controls_and_oversized_descriptions_still_fail_closed(bad_value):
    data = {**outline(), "architecture": bad_value}
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion(json.dumps(data)))

    provider = provider_for(handle)
    session = Session()
    try:
        with pytest.raises(ModelError, match="after one repair"):
            await provider.call(session, "planner:outline", OutlineProposal, "Plan.", {})
        assert len(requests) == len(session.usage) == 2
    finally:
        await provider.close()


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_output_limit_uses_one_compacting_repair_even_when_the_json_parses(repair_succeeds):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        response = completion(json.dumps(outline()))
        response["choices"][0]["finish_reason"] = (
            "stop" if repair_succeeds and len(requests) == 2 else "length"
        )
        return httpx.Response(200, json=response)

    provider = provider_for(handle)
    session = Session()
    try:
        if repair_succeeds:
            result = await provider.call(session, "planner:outline", OutlineProposal, "Plan.", {})
            assert result.phases[0].ref == "core"
        else:
            with pytest.raises(ModelError, match="output limit"):
                await provider.call(session, "planner:outline", OutlineProposal, "Plan.", {})
        assert len(requests) == len(session.usage) == 2
        assert requests[0]["max_tokens"] == requests[1]["max_tokens"] == 4096
        assert "concise" in requests[1]["messages"][-1]["content"].lower()
    finally:
        await provider.close()


async def test_complete_pipeline_validates_diagrams_sources_runner_graph_and_export(tmp_path):
    session = ready_session()
    session.mode = "live"
    store = Store(str(tmp_path / "sessions.db"))
    reviewed_framework(session)
    store.save(session)
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        payload = json.loads(body["messages"][1]["content"])
        if len(requests) == 1:
            response = completion('{"vision":')
            response["choices"][0]["finish_reason"] = "length"
            return httpx.Response(200, json=response)
        if "statements" in payload:
            role = "planner:verify"
        elif "phase" in payload:
            role = f"planner:phase:{payload['phase']['ref']}"
        elif "screen" in payload:
            role = f"planner:screen:{payload['screen']['ref']}"
        else:
            role = "planner:outline"
        result = demo_response(session, role, payload)
        diagram = "[Input] \u2192 [Save] \u2192 [Read]\n[Failure] \u2192 [Visible error]"
        if role == "planner:outline":
            result["architecture"] = diagram
            result["vision"]["text"] = "Synthetic \u201cworkflow\u201d: \u4fdd\u5b58"
        elif role.startswith("planner:screen:"):
            result["wireframes"] = {state: diagram for state in result["wireframes"]}
        elif role.startswith("planner:phase:"):
            result["flow"] = diagram
            for package in result["packages"]:
                package["flow"] = diagram
                for task in package["tasks"]:
                    task["checks"] = [{"command": list(TRUSTED_COMMAND), "expected": "No whitespace errors"}]
        return httpx.Response(200, json=completion(json.dumps(result)))

    provider = provider_for(handle)
    try:
        service = PlanningService(store, provider, provider.settings)
        events = [event async for event in service.generate(session)]
        assert events[-1]["type"] == "plan_ready"
        saved = store.get(session.id)
        identity = saved.planning.active
        assert saved.planning.approval is None and len(saved.planning.attempts) == 1
        assert len(saved.usage) == len(requests) == 6
        plan = store.get_plan(session.id, identity.plan_id, identity.revision)
        validate_plan(plan, saved.ledger)
        assert plan.outline.vision.text == "Synthetic \u201cworkflow\u201d: \u4fdd\u5b58"
        assert [source.source for source in plan.sources] == [item.source for item in session.ledger]
        for phase_ in plan.phases:
            for package in phase_.packages:
                preflight_checks(package)
        graph = project_graph(plan)
        assert graph["source"]["content_hash"] == identity.content_hash
        assert identity.content_hash in render_human(plan)
        assert identity.content_hash in render_engineering(plan)
        with pytest.raises(ValueError):
            export_bundle(plan, None, saved.revision, saved.ledger)
        # This is a test-only approval of a synthetic plan, never a live-session approval.
        archive_bytes = export_bundle(plan, identity, saved.revision, saved.ledger)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            for entry in manifest["artifacts"]:
                if entry["path"] != "manifest.json":
                    assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
        restored = store.get_plan(session.id, identity.plan_id, identity.revision)
        assert restored.content_hash == identity.content_hash
        assert provider.reserved[session.id] == 0
    finally:
        await provider.close()
