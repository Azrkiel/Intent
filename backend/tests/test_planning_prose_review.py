"""Review-routing evidence, not evidence of live model semantic judgment."""

import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.models import LiveModels
from backend.app.planning.contracts import PlanDocument, SourceItem
from backend.app.planning.demo import demo_response
from backend.app.planning.service import PlanningService
from backend.app.planning.validation import accept_phase, statement_catalog
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import outline, phase, ready_session, screen
from backend.tests.test_models import completion


def plan_fixture():
    from backend.app.planning.contracts import OutlineProposal, PhaseProposal

    session = ready_session()
    proposed = OutlineProposal.model_validate(outline(session))
    return PlanDocument(id="offline", revision=1, requirements_revision=1, mode="demo",
                        outline=proposed, screens=[screen()],
                        phases=[accept_phase(PhaseProposal.model_validate(phase()), proposed, 0),
                                accept_phase(PhaseProposal.model_validate(phase("app")), proposed, 1)],
                        sources=[SourceItem(**x.model_dump(
                            include={"id", "type", "text", "status", "source", "turn"}
                        )) for x in session.ledger])


def test_catalog_covers_prose_with_exact_paths_without_invented_citations():
    from backend.app.planning.review import review_catalog

    plan = plan_fixture()
    plan.outline.architecture = "a" * 12000
    before = plan.model_dump_json(round_trip=True)
    catalog = review_catalog(plan)
    old = statement_catalog(plan)
    assert {key: entry.text for key, entry in catalog.items() if key.startswith("S")} == {
        key: value.text for key, value in old.items()
    }
    paths = {tuple(entry.path): entry for entry in catalog.values()}
    expected = [
        ("outline", "architecture"), ("outline", "screens", 0, "title"),
        ("outline", "phases", 0, "title"), ("screens", 0, "wireframes", "empty"),
        ("phases", 0, "flow"), ("phases", 0, "packages", 0, "flow"),
        *(("phases", 0, "packages", 0, field, 0) for field in
          ("preconditions", "inputs", "outputs", "owned_paths", "artifacts")),
        ("phases", 0, "packages", 0, "tasks", 0, "title"),
        ("phases", 0, "packages", 0, "tasks", 0, "steps", 0),
        ("phases", 0, "packages", 0, "tasks", 0, "checks", 0, "expected"),
    ]
    for path in expected:
        entry = paths[path]
        assert entry.kind == "prose" and entry.ledger_ids is None and entry.status is None
        value = plan.model_dump()
        for token in path:
            value = value[token]
        assert entry.text == value
    assert not any("sources" in path or "command" in path or "depends_on" in path for path in paths)
    assert plan.model_dump_json(round_trip=True) == before
    assert review_catalog(plan) == catalog


def test_proposal_field_inventory_is_explicit():
    from backend.app.planning.contracts import (
        Check,
        LeafTaskProposal,
        OutlineProposal,
        PackageProposal,
        PhaseProposal,
        ScreenProposal,
    )

    expected = {
        OutlineProposal: {"vision", "journeys", "specification", "common_rules", "choices", "architecture",
                          "screens", "phases"},
        ScreenProposal: {"ref", "purpose", "wireframes"},
        PhaseProposal: {"ref", "goal", "flow", "packages"},
        PackageProposal: {"ref", "goal", "depends_on", "owned_paths", "produces", "consumes",
                          "preconditions", "inputs", "outputs", "flow", "tasks", "acceptance", "exclusions",
                          "choices", "artifacts"},
        LeafTaskProposal: {"title", "steps", "acceptance", "checks"},
        Check: {"command", "expected"},
    }
    for model, fields in expected.items():
        assert set(model.model_fields) == fields


@pytest.mark.parametrize("fault", ["missing_data", "read_failure", "open_choice", "placeholder"])
@pytest.mark.parametrize("verdict", ["reject", "omit"])
async def test_unsupported_prose_rejection_or_omission_blocks_readiness(tmp_path, fault, verdict):
    session = ready_session()
    session.mode = "live"
    store = Store(str(tmp_path / "test.sqlite3"))
    store.save(session)
    seen = Counter()
    # Minimal text from the captured failure; this scripted verdict is a routing test.
    bad = {
        "missing_data": "Handle corrupt or missing data by showing an error and treating the value as 0.",
        "read_failure": "If the read throws an exception, treat the value as 0.",
        "open_choice": "Update the display before persisting while the update strategy remains unresolved.",
        "placeholder": "None",
    }[fault]
    observed = []

    def handle(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        role = ("planner:verify" if "statements" in payload else
                f"planner:phase:{payload['phase']['ref']}" if "phase" in payload else
                f"planner:screen:{payload['screen']['ref']}" if "screen" in payload else "planner:outline")
        seen[role] += 1
        result = demo_response(session, role, payload)
        if role == "planner:phase:foundation":
            if fault == "placeholder":
                result["packages"][0]["inputs"] = [bad]
            else:
                result["packages"][0]["tasks"][0]["steps"][0] = bad
        if role == "planner:verify":
            matches = [key for key, entry in payload["statements"].items() if entry["text"] == bad]
            observed.extend(matches)
            assert len(matches) == 1, "Faulty task prose must have an explicit review address"
            if verdict == "reject":
                result["rejected_statement_ids"] = matches
            else:
                result["reviewed_statement_ids"].remove(matches[0])
        return httpx.Response(200, json=completion(json.dumps(result)))

    client = AsyncOpenAI(api_key="offline", base_url="https://test.invalid/v1", max_retries=0,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    models = LiveModels(Settings(mode="live", _env_file=None), client=client)
    try:
        events = [event async for event in PlanningService(store, models, models.settings).generate(session)]
        assert events[-1]["type"] == "plan_error"
        assert observed and seen["planner:verify"] == (1 if verdict == "reject" else 2)
        assert session.planning.active is session.planning.approval is None
        assert store.get(session.id).planning.status == "blocked"
    finally:
        await models.close()


def test_review_capacity_includes_uncited_prose():
    from backend.app.planning.review import review_catalog

    plan = plan_fixture()
    packet = plan.phases[0].packages[0]
    # Deliberately construct an oversized in-memory catalog, without a provider.
    packet.inputs = [f"Input {i}" for i in range(501)]
    with pytest.raises(ValueError, match="semantic verification capacity"):
        review_catalog(plan)
