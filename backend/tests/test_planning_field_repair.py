"""Offline provider-boundary regressions for application-scoped replacements."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from backend.app.domain import Session
from backend.app.models import LiveModels, ModelError
from backend.app.planning.contracts import PhaseProposal
from backend.app.planning.repair import FieldRepair, ScopedError
from backend.app.planning.service import checked_schema
from backend.app.settings import Settings
from backend.tests.planning_fixtures import phase
from backend.tests.test_models import completion


def captured_shape():
    """Minimal sanitized attempt-8 shape; no private session is required."""
    value = phase()
    packet = value["packages"][0]
    packet["preconditions"] = []
    packet["inputs"] = []
    packet["tasks"] = [copy.deepcopy(packet["tasks"][0]) for _ in range(3)]
    for index, task in enumerate(packet["tasks"], 1):
        task["title"] = f"Task {index}"
    return value


def provider(responses, requests, settings=None):
    def handle(request):
        requests.append(json.loads(request.content))
        value = responses[len(requests) - 1]
        return httpx.Response(200, json=completion(value if isinstance(value, str) else json.dumps(value)))

    client = AsyncOpenAI(api_key="offline", base_url="https://test.invalid/v1", max_retries=0,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    return LiveModels(settings or Settings(_env_file=None), client=client)


async def test_two_field_repair_preserves_original_three_tasks_and_all_siblings():
    original = captured_shape()
    saved = copy.deepcopy(original)
    requests = []
    session = Session()
    models = provider([original, {"R1": ["Requirements approved"], "R2": ["Accepted outline"]}], requests)
    try:
        result = await models.call(session, "planner:phase:core", PhaseProposal, "Plan.", {})
        expected = copy.deepcopy(original)
        expected["packages"][0]["preconditions"] = ["Requirements approved"]
        expected["packages"][0]["inputs"] = ["Accepted outline"]
        assert result.model_dump() == expected
        assert original == saved
        repair = json.loads(requests[1]["messages"][-1]["content"])
        assert repair["mode"] == "field_repair"
        assert [x["path"] for x in repair["repair_fields"].values()] == [
            ["packages", 0, "preconditions"], ["packages", 0, "inputs"],
        ]
        assert all(field["original"] == [] for field in repair["repair_fields"].values())
        assert len(requests) == len(session.usage) == 2
        assert requests[0]["max_tokens"] == requests[1]["max_tokens"] == 4096
        assert models.reserved[session.id] == 0
    finally:
        await models.close()


@pytest.mark.parametrize("replacement", [
    {"R1": [], "R2": ["Outline"]},
    {"R1": ["Approved"], "R2": ["Outline"], "tasks": []},
    {"R1": ["Approved"]},
    {"path": ["packages", 0], "value": {}},
    '{"R1":["Approved"],"R1":["Different"],"R2":["Outline"]}',
    '{"R1":',
])
async def test_invalid_replacements_stop_after_two_responses(replacement):
    requests = []
    session = Session()
    models = provider([captured_shape(), replacement], requests)
    try:
        with pytest.raises(ModelError, match="after one repair"):
            await models.call(session, "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(requests) == len(session.usage) == 2
        assert models.reserved[session.id] == 0
    finally:
        await models.close()


async def test_full_object_duplicate_task_response_cannot_replace_a_valid_task_list():
    original = captured_shape()
    bad = copy.deepcopy(original)
    packet = bad["packages"][0]
    packet["preconditions"] = packet["inputs"] = ["None"]
    packet["tasks"] *= 2
    requests = []
    models = provider([original, bad], requests)
    try:
        with pytest.raises(ModelError, match="after one repair"):
            await models.call(Session(), "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(requests) == 2
    finally:
        await models.close()


async def test_unscoped_root_failure_gets_one_complete_retry_and_no_field_repair():
    def root_failure(value):
        raise ValueError("Unmapped cross-field failure")

    requests = []
    models = provider([phase(), phase()], requests)
    try:
        with pytest.raises(ModelError, match="deterministic acceptance after one repair"):
            await models.call(Session(), "planner:phase:core", checked_schema(PhaseProposal, root_failure),
                              "Plan.", {})
        assert len(requests) == 2
        retry = requests[1]["messages"][-1]["content"]
        assert retry.startswith("Correct all schema validation errors") and "field_repair" not in retry
    finally:
        await models.close()


@pytest.mark.parametrize("original", [
    {**phase(), "notes": "Unexpected key"},
    json.dumps(phase())[:-1] + ', "ref": "core"}',
])
async def test_unscopable_model_output_gets_one_complete_retry(original):
    requests = []
    session = Session()
    models = provider([original, phase()], requests)
    try:
        result = await models.call(session, "planner:phase:core", PhaseProposal, "Plan.", {})
        assert result.model_dump() == phase()
        assert len(requests) == len(session.usage) == 2
        assert "field_repair" not in requests[1]["messages"][-1]["content"]
    finally:
        await models.close()


async def test_reconstructed_whole_object_is_checked_without_a_third_response():
    def acceptance(value):
        if value.packages[0].inputs == ["Unsupported source"]:
            raise ValueError("Independent source check rejected")

    requests = []
    models = provider([captured_shape(), {"R1": ["Approved"], "R2": ["Unsupported source"]}], requests)
    try:
        with pytest.raises(ModelError, match="deterministic acceptance after one repair"):
            await models.call(Session(), "planner:phase:core", checked_schema(PhaseProposal, acceptance),
                              "Plan.", {})
        assert len(requests) == 2
    finally:
        await models.close()


async def test_cancellation_of_repair_releases_budget_reservation():
    requests = []
    models = provider([captured_shape()], requests)
    original_completion = models.completion

    async def cancel_second(*args, **kwargs):
        if requests:
            raise asyncio.CancelledError
        return await original_completion(*args, **kwargs)

    models.completion = cancel_second
    session = Session()
    try:
        with pytest.raises(asyncio.CancelledError):
            await models.call(session, "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(session.usage) == 1 and models.reserved[session.id] == 0
    finally:
        await models.close()


@pytest.mark.parametrize("paths", [
    [()], [("packages", -1, "inputs")], [("packages", True, "inputs")],
    [("packages", 0, "unknown")], [("packages", 0, "inputs", 99)],
    [("packages",), ("packages", 0, "inputs")],
])
async def test_ambiguous_or_overlapping_application_scopes_do_not_authorize_repair(paths):
    def check(value):
        raise ScopedError("Cross-field error", *paths)

    requests = []
    models = provider([phase()], requests)
    try:
        with pytest.raises(ModelError, match="cannot be safely scoped"):
            await models.call(Session(), "planner:phase:core", checked_schema(PhaseProposal, check),
                              "Plan.", {})
        assert len(requests) == 1
    finally:
        await models.close()


def test_repeated_scopes_coalesce_and_missing_field_parent_must_exist():
    original = phase()
    del original["packages"][0]["inputs"]
    with pytest.raises(ValidationError) as caught:
        PhaseProposal.model_validate(original)
    repair = FieldRepair(PhaseProposal, original, caught.value)
    assert repair.apply('{"R1":["Accepted source ledger"]}').packages[0].inputs == ["Accepted source ledger"]
    assert "inputs" not in original["packages"][0]

    def duplicate_scope(value):
        raise ScopedError("Wrong source", ("packages", 0, "inputs"), ("packages", 0, "inputs"))

    schema = checked_schema(PhaseProposal, duplicate_scope)
    with pytest.raises(ValidationError) as caught:
        schema.model_validate(phase())
    assert len(FieldRepair(schema, phase(), caught.value).paths) == 1


async def test_independent_task_limit_is_preserved_in_replacement_schema():
    original = captured_shape()
    original["packages"][0]["tasks"].append(copy.deepcopy(original["packages"][0]["tasks"][0]))
    requests = []
    models = provider([original, {"R1": ["Approved"], "R2": ["Outline"],
                                 "R3": original["packages"][0]["tasks"]}], requests)
    try:
        with pytest.raises(ModelError, match="schema validation after one repair"):
            await models.call(Session(), "planner:phase:core", PhaseProposal, "Plan.", {})
        schema = json.loads(requests[-1]["messages"][0]["content"].rsplit("\n", 1)[1])
        assert schema["properties"]["R3"]["maxItems"] == 3
        assert "schema" not in json.loads(requests[-1]["messages"][-1]["content"])
    finally:
        await models.close()


async def test_budget_is_rechecked_before_the_repair_request():
    requests = []
    models = provider([captured_shape()], requests)
    complete = models.completion

    async def exhaust_budget(*args, **kwargs):
        response = await complete(*args, **kwargs)
        models.settings.session_budget_usd = 0.000001
        return response

    models.completion = exhaust_budget
    session = Session()
    try:
        with pytest.raises(ModelError, match="budget"):
            await models.call(session, "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(requests) == len(session.usage) == 1 and models.reserved[session.id] == 0
    finally:
        await models.close()


async def test_output_limit_on_replacement_stops_without_applying_values():
    requests = []
    models = provider([captured_shape(), {"R1": ["Approved"], "R2": ["Outline"]}], requests)
    complete = models.completion

    async def limit_repair(*args, **kwargs):
        response = await complete(*args, **kwargs)
        if len(requests) == 2:
            response.choices[0].finish_reason = "length"
        return response

    models.completion = limit_repair
    try:
        with pytest.raises(ModelError, match="output limit after one repair"):
            await models.call(Session(), "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(requests) == 2
    finally:
        await models.close()


async def test_schema_failure_is_not_reported_as_invalid_json():
    requests = []
    models = provider([captured_shape(), {"R1": [], "R2": []}], requests)
    try:
        with pytest.raises(ModelError, match="schema validation") as caught:
            await models.call(Session(), "planner:phase:core", PhaseProposal, "Plan.", {})
        assert "valid JSON" not in str(caught.value)
    finally:
        await models.close()


async def test_wrong_top_level_shape_is_a_schema_failure_not_an_acceptance_failure():
    requests = []
    models = provider(["not JSON", "[]"], requests)
    try:
        with pytest.raises(ModelError, match="schema validation after one repair"):
            await models.call(Session(), "planner:phase:core", PhaseProposal, "Plan.", {})
        assert len(requests) == 2
    finally:
        await models.close()


def test_dependency_error_scope_identifies_the_offending_package_not_its_consumer():
    from backend.app.planning.contracts import OutlineProposal, PlanDocument, SourceItem
    from backend.app.planning.validation import accept_phase, validate_plan
    from backend.tests.planning_fixtures import outline, package, ready_session, screen

    session = ready_session()
    accepted_outline = OutlineProposal.model_validate(outline())
    draft = phase(packages=[package("consumer", "consumer", ["producer"]),
                            package("producer", "producer", ["unknown"])])
    plan = PlanDocument(id="offline", revision=1, requirements_revision=1, mode="demo",
                        outline=accepted_outline, screens=[screen()],
                        phases=[accept_phase(PhaseProposal.model_validate(draft), accepted_outline, 0)],
                        sources=[SourceItem(**x.model_dump(
                            include={"id", "type", "text", "status", "source", "turn"}
                        )) for x in session.ledger])
    with pytest.raises(ScopedError) as caught:
        validate_plan(plan, session.ledger, complete=False)
    assert caught.value.paths == (("phases", 0, "packages", 1, "depends_on"),)
