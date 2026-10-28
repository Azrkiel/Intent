"""Complete human graph: deterministic projections, never a second planning pass.

Canonical node IDs are scoped by ``source``. Presentation state is deliberately
outside the immutable PlanDocument and cannot confer execution/plan approval.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import PlanAttempt, PlanDocument, SourceItem, content_hash
from .validation import (
    accept_outline,
    accept_phase,
    accept_screen,
    check_citations,
    validate_plan,
)

SCHEMA = "plan-graph-v1"
STATES = {"draft", "planning", "review_ready", "approved", "blocked", "stale"}


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["root", "phase", "package", "task", "screen"]
    parent_id: str | None
    title: str
    status: Literal["validated", "pending"]
    body: dict
    source_paths: list[str]
    citations: list[str]


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source: str
    target: str
    type: Literal["contains", "depends_on", "attachment"]
    provenance: str


class PlanGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_schema_version: Literal["plan-graph-v1"] = SCHEMA
    source: dict
    state: Literal["draft", "planning", "review_ready", "approved", "blocked", "stale"]
    partial: bool
    root_id: Literal["root"] = "root"
    nodes: list[GraphNode] = Field(max_length=40)
    edges: list[GraphEdge] = Field(max_length=128)
    source_fields: dict[str, dict[str, str]]


def _token(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def _citations(value):
    if isinstance(value, dict):
        yield from value.get("ledger_ids", [])
        for key, child in value.items():
            if key != "ledger_ids":
                yield from _citations(child)
    elif isinstance(value, list):
        for child in value:
            yield from _citations(child)


def _project(document, *, state, partial, provenance_notice=None, worker_limits=None):
    if state not in STATES:
        raise ValueError("Unknown graph presentation state")
    raw = document.model_dump(mode="json", round_trip=True)
    graph = {
        "graph_schema_version": SCHEMA,
        "source": {
            "plan_id": document.id,
            "revision": document.revision,
            "requirements_revision": document.requirements_revision,
            "content_hash": content_hash(raw),
            "mode": document.mode,
        },
        "state": state,
        "partial": partial,
        "root_id": "root",
        "nodes": [],
        "edges": [],
        "source_fields": {},
    }

    def node(id, kind, title, parent_id, body, *, pending=False):
        value = {
            "id": id, "kind": kind, "title": title, "parent_id": parent_id,
            "status": "pending" if pending else "validated", "body": body,
            "source_paths": [], "citations": sorted(set(_citations(body))),
        }
        graph["nodes"].append(value)
        if parent_id:
            edge(parent_id, id, "attachment" if kind == "screen" else "contains",
                 "Application-owned containment over canonical source fields")
        return value

    def edge(source, target, kind, provenance):
        graph["edges"].append({
            "id": f"{kind}:{source}:{target}", "source": source, "target": target,
            "type": kind, "provenance": provenance,
        })

    def source(value, source_path, body_path, owner):
        owner["source_paths"].append(source_path)

        def visit(item, path, destination):
            if isinstance(item, dict) and item:
                for key, child in item.items():
                    visit(child, path + "/" + _token(key), destination + "/" + _token(key))
            elif isinstance(item, list) and item:
                for index, child in enumerate(item):
                    visit(child, f"{path}/{index}", f"{destination}/{index}")
            else:
                if path in graph["source_fields"]:
                    raise ValueError("Source field has multiple graph owners")
                graph["source_fields"][path] = {"node_id": owner["id"], "body_path": destination}

        visit(value, source_path, body_path)

    identity = {key: raw[key] for key in ("id", "revision", "requirements_revision", "mode")}
    identity["content_hash"] = graph["source"]["content_hash"]
    root = node("root", "root", "Project intent and orchestration", None, {
        "identity": identity,
        "outline": {key: val for key, val in raw["outline"].items() if key not in {"phases", "screens"}},
        "sources": raw["sources"],
        "orchestration": {
            "provenance": "Application-owned scheduling policy; no worker completion evidence",
            "dispatch_unit": "work package",
            "phase_order": [f"P{i}" for i in range(1, len(document.outline.phases) + 1)],
            "eligibility": [
                "Approve the current requirements and exact complete plan.",
                "Earlier phases require explicit human acceptance.",
                "Package dependencies require trusted integration and current shared inputs.",
                "Review the exact ancestor context before dispatch.",
            ],
            "stop_gates": [
                "Unsupported checks, stale context, scope failures, and uncertain outcomes block execution.",
                "Worker completion is a claim. Trusted evidence precedes human phase acceptance.",
                "Starting a later phase requires an explicit action.",
            ],
            "worker_limits": worker_limits or {"per_session": 1, "global": 2},
            "view_boundary": "Human overview includes all branches; worker bundles are separate projections.",
        },
    })
    if provenance_notice:
        root["body"]["provenance_notice"] = provenance_notice
    for key in ("id", "revision", "requirements_revision", "mode"):
        source(raw[key], f"/{key}", f"/identity/{key}", root)
    source(raw["sources"], "/sources", "/sources", root)
    for key, value in root["body"]["outline"].items():
        source(value, f"/outline/{_token(key)}", f"/outline/{_token(key)}", root)
    if not raw["outline"]["screens"]:
        root["body"]["outline"]["screens"] = []
        source([], "/outline/screens", "/outline/screens", root)
    for section in ("phases", "screens"):
        if not raw[section]:
            root["body"]["accepted_" + section] = []
            source([], "/" + section, "/accepted_" + section, root)

    phase_ids = {item.ref: f"P{i}" for i, item in enumerate(document.outline.phases, 1)}
    package_ids = {item.ref: item.id for phase in document.phases for item in phase.packages}
    for index, reference in enumerate(document.outline.phases):
        id = phase_ids[reference.ref]
        phase = next((p for p in document.phases if p.ref == reference.ref), None)
        body = {
            "outline_ref": raw["outline"]["phases"][index],
            "phase": None,
            "gate": "Inspect trusted package/aggregate evidence and obtain explicit human phase acceptance.",
        }
        if phase is not None:
            phase_index = document.phases.index(phase)
            phase_raw = raw["phases"][phase_index]
            body["phase"] = {k: v for k, v in phase_raw.items() if k != "packages"}
        phase_node = node(id, "phase", reference.title, "root", body, pending=phase is None)
        source(body["outline_ref"], f"/outline/phases/{index}", "/outline_ref", phase_node)
        for dependency_index, dependency in enumerate(reference.depends_on):
            edge(id, phase_ids[dependency], "depends_on",
                 f"/outline/phases/{index}/depends_on/{dependency_index}")
        if phase is None:
            continue
        for key, value in body["phase"].items():
            source(value, f"/phases/{phase_index}/{key}", f"/phase/{key}", phase_node)
        for package_index, package in enumerate(phase.packages):
            package_raw = phase_raw["packages"][package_index]
            package_body = {k: v for k, v in package_raw.items() if k != "tasks"}
            package_node = node(package.id, "package", package.goal.text, id, {
                "package": package_body,
                "dependency_ids": [package_ids[ref] for ref in package.depends_on],
                "handoff": {
                    "status": "planned",
                    "provenance": "Application-owned outgoing report contract; worker reports remain claims",
                    "required_fields": [
                        "plan and context identities", "package and phase attempt", "changed paths",
                        "artifact hashes", "interface versions", "base and integrated commits",
                        "trusted evidence references", "unresolved decisions", "failure/cancellation state",
                        "next prerequisite and gate",
                    ],
                },
            })
            package_path = f"/phases/{phase_index}/packages/{package_index}"
            for key, value in package_body.items():
                source(value, package_path + "/" + key, "/package/" + key, package_node)
            for dep_index, dependency in enumerate(package.depends_on):
                edge(package.id, package_ids[dependency], "depends_on",
                     package_path + f"/depends_on/{dep_index}")
            for task_index, task in enumerate(package.tasks):
                task_raw = package_raw["tasks"][task_index]
                task_node = node(task.id, "task", task.title, package.id, {"task": task_raw})
                source(task_raw, package_path + f"/tasks/{task_index}", "/task", task_node)

    for index, reference in enumerate(document.outline.screens):
        screen = next((s for s in document.screens if s.ref == reference.ref), None)
        body = {"outline_ref": raw["outline"]["screens"][index], "screen": None}
        if screen is not None:
            screen_index = document.screens.index(screen)
            body["screen"] = raw["screens"][screen_index]
        screen_node = node(f"screen-{index + 1}", "screen", reference.title, "root", body,
                           pending=screen is None)
        source(body["outline_ref"], f"/outline/screens/{index}", "/outline_ref", screen_node)
        if screen is not None:
            source(body["screen"], f"/screens/{screen_index}", "/screen", screen_node)
    return PlanGraph.model_validate(graph).model_dump(mode="json")


def project_graph(plan: PlanDocument, ledger=None, *, state="review_ready", worker_limits=None):
    """Project a complete validated source; presentation state does not alter its hash."""
    validate_plan(plan, plan.sources if ledger is None else ledger)
    return _project(plan, state=state, partial=False, worker_limits=worker_limits)


def project_attempt(
    attempt: PlanAttempt, ledger, *, mode, state, current_revision=None, worker_limits=None,
):
    """Accepted sections only. Early attempts can lack screens and all phase bodies."""
    if attempt.outline is None:
        return None
    stale = current_revision is not None and attempt.requirements_revision != current_revision
    sources = [] if stale else [SourceItem(**item.model_dump(
        include={"id", "type", "text", "status", "source", "turn"},
    )) for item in ledger]
    if not stale:
        accept_outline(attempt.outline, ledger)
        check_citations(attempt, ledger)
    if [s.ref for s in attempt.screens] != [s.ref for s in attempt.outline.screens[:len(attempt.screens)]]:
        raise ValueError("Partial graph screens differ from accepted outline order")
    for screen in attempt.screens:
        accept_screen(screen, attempt.outline, screen.ref)
    for index, phase in enumerate(attempt.phases):
        from .contracts import PhaseProposal

        proposal = PhaseProposal.model_validate(phase.model_dump(exclude={"id", "packages"}) | {
            "packages": [package.model_dump(exclude={"id", "tasks"}) | {
                "tasks": [task.model_dump(exclude={"id"}) for task in package.tasks],
            } for package in phase.packages],
        })
        if accept_phase(proposal, attempt.outline, index) != phase:
            raise ValueError("Partial graph canonical IDs changed")
    document = PlanDocument(
        id=attempt.plan_id, revision=attempt.revision, requirements_revision=attempt.requirements_revision,
        mode=mode, outline=attempt.outline, screens=attempt.screens, phases=attempt.phases, sources=sources,
    )
    if attempt.phases and not stale:
        validate_plan(document, ledger, complete=False)
    return _project(
        document, state="stale" if stale else state, partial=True, worker_limits=worker_limits,
        provenance_notice=(
            "Historical source snapshot unavailable for this stale accepted attempt." if stale else None
        ),
    )
