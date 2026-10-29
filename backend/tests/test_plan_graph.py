import copy
import json

import pytest

from backend.app.planning.contracts import PlanAttempt
from backend.app.planning.graph import project_attempt, project_graph
from backend.tests.test_plan_validation import plan


def leaves(value, path=""):
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from leaves(item, path + "/" + key.replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            yield from leaves(item, f"{path}/{index}")
    else:
        yield path, value


def pointer(value, path):
    for part in path.lstrip("/").split("/") if path else []:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def test_every_source_field_is_discoverable_without_changing_the_document():
    session, document = plan()
    before = document.model_dump_json(round_trip=True)
    digest = document.content_hash
    graph = project_graph(document, session.ledger)
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert graph["graph_schema_version"] == "plan-graph-v1"
    assert graph["source"]["content_hash"] == digest
    assert graph["source"]["mode"] == "demo"
    assert graph["root_id"] == "root"
    assert graph["partial"] is False
    assert graph["state"] == "review_ready"
    assert document.model_dump_json(round_trip=True) == before
    assert document.content_hash == digest
    for path, expected in leaves(document.model_dump(mode="json", round_trip=True)):
        address = graph["source_fields"][path]
        assert pointer(nodes[address["node_id"]]["body"], address["body_path"]) == expected, path
    assert {node["kind"] for node in nodes.values()} == {"root", "phase", "package", "task", "screen"}
    root = nodes["root"]
    assert "orchestration" in root["body"]
    assert root["body"]["sources"][0]["source"] == document.sources[0].source
    assert nodes["P1-W1"]["body"]["handoff"]["status"] == "planned"


def test_containment_dependencies_citations_and_ids_are_deterministic():
    session, document = plan()
    graph = project_graph(document, session.ledger)
    assert graph == project_graph(document, session.ledger)
    assert len([n for n in graph["nodes"] if n["kind"] == "root"]) == 1
    for node in graph["nodes"]:
        parents = [e for e in graph["edges"] if e["type"] == "contains" and e["target"] == node["id"]]
        assert len(parents) == (0 if node["kind"] in {"root", "screen"} else 1)
        if parents:
            assert parents[0]["source"] == node["parent_id"]
    dependencies = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "depends_on"}
    assert dependencies == {("P2", "P1"), ("P2-W1", "P1-W1")}
    assert all(edge["provenance"] for edge in graph["edges"])
    assert all("L1" in n["citations"] for n in graph["nodes"] if n["kind"] in {"package", "task"})


def test_partial_attempt_keeps_pending_references_and_never_fabricates_packages():
    session, document = plan()
    attempt = PlanAttempt(
        plan_id=document.id, revision=1, requirements_revision=1,
        outline=document.outline, screens=[document.screens[0]], error="Rejected phase reference",
    )
    graph = project_attempt(attempt, session.ledger, mode="demo", state="blocked")
    assert graph["partial"] and graph["state"] == "blocked"
    assert graph["source"]["requirements_revision"] == 1
    assert {n["id"] for n in graph["nodes"]} == {"root", "P1", "P2", "screen-1"}
    assert all(n["status"] == "pending" for n in graph["nodes"] if n["kind"] == "phase")
    assert not any(n["kind"] in {"package", "task"} for n in graph["nodes"])
    attempt.screens = []
    graph = project_attempt(attempt, session.ledger, mode="demo", state="planning")
    assert next(n for n in graph["nodes"] if n["kind"] == "screen")["status"] == "pending"
    attempt.outline = None
    assert project_attempt(attempt, session.ledger, mode="demo", state="blocked") is None


def test_partial_phase_preserves_accepted_body_and_sources():
    session, document = plan()
    attempt = PlanAttempt(
        plan_id=document.id, revision=1, requirements_revision=1,
        outline=document.outline, screens=document.screens, phases=document.phases[:1],
    )
    graph = project_attempt(attempt, session.ledger, mode="demo", state="planning")
    assert next(n for n in graph["nodes"] if n["id"] == "P1")["status"] == "validated"
    assert next(n for n in graph["nodes"] if n["id"] == "P2")["status"] == "pending"
    own = next(n for n in graph["nodes"] if n["id"] == "P1-W1")
    assert own["body"]["package"]["owned_paths"] == ["contracts.py"]


@pytest.mark.parametrize("damage", ["id", "dependency", "citation", "missing_phase", "missing_screen"])
def test_complete_graph_rejects_malformed_source(damage):
    session, document = plan()
    if damage == "id":
        document.phases[0].id = "P99"
    elif damage == "dependency":
        document.phases[0].packages[0].depends_on = ["unknown"]
    elif damage == "citation":
        document.outline.vision.ledger_ids = ["unknown"]
    elif damage == "missing_phase":
        document.phases = []
    else:
        document.screens = []
    with pytest.raises(ValueError):
        project_graph(document, session.ledger)


def test_stale_overlay_and_unicode_do_not_change_source_hash():
    session, document = plan()
    document.outline.vision.text = "保存 notes </script>"
    digest = document.content_hash
    fresh = project_graph(document, session.ledger, state="approved")
    stale = project_graph(document, session.ledger, state="stale")
    assert stale["source"] == fresh["source"]
    assert stale["nodes"] == fresh["nodes"]
    assert "保存" in json.dumps(fresh, ensure_ascii=False)
    assert document.content_hash == digest
    invalid = copy.deepcopy(document)
    invalid.sources[0].source = "Changed quote"
    with pytest.raises(ValueError):
        project_graph(invalid, session.ledger)


def test_stale_attempt_does_not_attach_a_newer_ledger_as_historical_quotes():
    session, document = plan()
    attempt = PlanAttempt(
        plan_id=document.id, revision=1, requirements_revision=1,
        outline=document.outline, screens=document.screens, phases=document.phases[:1],
    )
    session.ledger[0].source = "Newer source quote"
    graph = project_attempt(attempt, session.ledger, mode="demo", state="stale", current_revision=2)
    assert graph["state"] == "stale" and graph["partial"]
    assert graph["nodes"][0]["body"]["sources"] == []
    assert "snapshot unavailable" in graph["nodes"][0]["body"]["provenance_notice"].lower()
    assert "Newer source quote" not in json.dumps(graph)
