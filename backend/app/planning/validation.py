"""Deterministic checks; a model's claim of independence is never sufficient."""

from pathlib import PurePosixPath

from pydantic import BaseModel, TypeAdapter

from .contracts import (
    Diagram,
    LeafTask,
    OutlineProposal,
    Package,
    Phase,
    PhaseProposal,
    PlanDocument,
    ScreenProposal,
    Statement,
)
from .repair import ScopedError
from .review import review_catalog


def safe_path(path: str) -> str:
    parts = path.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}
    if (
        PurePosixPath(path).is_absolute()
        or any(c in path for c in '\\:*?"<>|')
        or any(ord(c) < 32 for c in path)
        or any(
            p in {"", ".", ".."} or p[-1:] in {" ", "."} or p.split(".")[0].upper() in reserved for p in parts
        )
    ):
        raise ValueError("Unsafe relative artifact or ownership path")
    return path


def statement_paths(value, path=()):
    """Stable, application-generated addresses for every statement in a proposal."""
    if isinstance(value, Statement):
        yield path, value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from statement_paths(getattr(value, name), path + (name,))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from statement_paths(item, path + (index,))


def statements(value):
    for _, statement in statement_paths(value):
        yield statement


def statement_catalog(plan: PlanDocument) -> dict[str, Statement]:
    return {f"S{i}": value for i, value in enumerate(statements(plan), 1)}


def check_citations(value, ledger):
    items = {x.id: x for x in ledger}
    for path, claim in statement_paths(value):
        if not set(claim.ledger_ids) <= items.keys():
            raise ScopedError("Unknown ledger citation", path + ("ledger_ids",))
        if claim.status == "confirmed" and any(items[id].status != "confirmed" for id in claim.ledger_ids):
            raise ScopedError("Confirmed statement cites an unconfirmed source", path + ("status",))


def ancestors(graph: dict[str, list[str]], node: str, visiting=None, scopes=None) -> set[str]:
    visiting = set() if visiting is None else visiting
    if node in visiting:
        if scopes is not None:
            raise ScopedError("Dependency cycle", scopes[node])
        raise ValueError("Dependency cycle")
    if node not in graph:
        raise ValueError("Unknown dependency")
    visiting = visiting | {node}
    result = set()
    for dependency in graph[node]:
        if dependency not in graph and scopes is not None:
            raise ScopedError("Unknown dependency", scopes[node])
        result.add(dependency)
        result.update(ancestors(graph, dependency, visiting, scopes))
    return result


def unique(values):
    if len(values) != len(set(values)):
        raise ValueError("Duplicate proposal reference")


_description = TypeAdapter(Diagram)


def check_diagram(diagram: str):
    _description.validate_python(diagram)


def accept_outline(outline: OutlineProposal, ledger) -> OutlineProposal:
    check_diagram(outline.architecture)
    check_citations(outline, ledger)
    unique([p.ref for p in outline.phases] + [s.ref for s in outline.screens])
    graph = {p.ref: p.depends_on for p in outline.phases}
    scopes = {p.ref: ("phases", i, "depends_on") for i, p in enumerate(outline.phases)}
    for i, phase in enumerate(outline.phases):
        earlier = {p.ref for p in outline.phases[:i]}
        try:
            if not ancestors(graph, phase.ref, scopes=scopes) <= earlier:
                raise ValueError("Phase depends on a later phase")
        except ScopedError:
            raise
        except ValueError as error:
            raise ScopedError(str(error), ("phases", i, "depends_on")) from error
    required = {x.id for x in ledger if x.status == "confirmed"}
    covered = {id for s in outline.specification if s.status == "confirmed" for id in s.ledger_ids}
    if not required <= covered:
        raise ScopedError("Specification misses confirmed requirements", ("specification",))
    unresolved = {x.id for x in ledger if x.status != "confirmed"}
    visible = {id for s in outline.choices if s.status != "confirmed" for id in s.ledger_ids}
    if not unresolved <= visible:
        raise ScopedError("Unconfirmed ledger items must remain visible as proposed or unresolved choices",
                          ("choices",))
    rules = {id for s in outline.common_rules for id in s.ledger_ids}
    if (
        not {x.id for x in ledger if x.status == "confirmed" and x.type in {"constraint", "non-goal"}}
        <= rules
    ):
        raise ScopedError("Common rules miss constraints or exclusions", ("common_rules",))
    for screen in outline.screens:
        unique(screen.states)
    return outline


def accept_screen(screen: ScreenProposal, outline: OutlineProposal, ref: str) -> ScreenProposal:
    expected = next((s for s in outline.screens if s.ref == ref), None)
    if expected is None:
        raise ValueError("Screen does not match accepted outline states")
    if screen.ref != ref:
        raise ScopedError("Screen does not match accepted outline states", ("ref",))
    if set(screen.wireframes) != set(expected.states):
        raise ScopedError("Screen does not match accepted outline states", ("wireframes",))
    for diagram in screen.wireframes.values():
        check_diagram(diagram)
    return screen


def accept_phase(phase: PhaseProposal, outline: OutlineProposal, index: int) -> Phase:
    if index >= len(outline.phases) or outline.phases[index].ref != phase.ref:
        raise ValueError("Phase does not match accepted outline")
    check_diagram(phase.flow)
    for package in phase.packages:
        check_diagram(package.flow)
    phase_id = f"P{index + 1}"
    packages = []
    for i, package in enumerate(phase.packages, 1):
        package_id = f"{phase_id}-W{i}"
        tasks = [LeafTask(**t.model_dump(), id=f"{package_id}-T{j}") for j, t in enumerate(package.tasks, 1)]
        packages.append(Package(**package.model_dump(exclude={"tasks"}), id=package_id, tasks=tasks))
    return Phase(**phase.model_dump(exclude={"packages"}), id=phase_id, packages=packages)


def overlaps(left: str, right: str) -> bool:
    left, right = left.casefold(), right.casefold()
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def validate_plan(plan: PlanDocument, ledger, *, complete: bool = True):
    accept_outline(plan.outline, ledger)
    check_citations(plan, ledger)
    sources = [x.model_dump(include={"id", "type", "text", "status", "source", "turn"}) for x in ledger]
    if [x.model_dump() for x in plan.sources] != sources:
        raise ValueError("Plan source snapshot differs from the current ledger")
    expected_phases = plan.outline.phases if complete else plan.outline.phases[: len(plan.phases)]
    if [p.ref for p in plan.phases] != [p.ref for p in expected_phases]:
        raise ValueError("Incomplete or changed phases")
    if [s.ref for s in plan.screens] != [s.ref for s in plan.outline.screens]:
        raise ValueError("Incomplete or changed screens")
    for screen in plan.screens:
        accept_screen(screen, plan.outline, screen.ref)
    packages = [w for p in plan.phases for w in p.packages]
    locations = {w.ref: ("phases", pi, "packages", wi)
                 for pi, p in enumerate(plan.phases) for wi, w in enumerate(p.packages)}
    unique([w.ref for w in packages])
    graph = {w.ref: w.depends_on for w in packages}
    scopes = {ref: path + ("depends_on",) for ref, path in locations.items()}
    reachable = {ref: ancestors(graph, ref, scopes=scopes) for ref in graph}
    phase_graph = {p.ref: p.depends_on for p in plan.outline.phases}
    phase_reachable = {ref: ancestors(phase_graph, ref) for ref in phase_graph}
    owner = {w.ref: p.ref for p in plan.phases for w in p.packages}
    order = {p.ref: i for i, p in enumerate(plan.phases)}
    required = {x.id for x in ledger if x.status == "confirmed"}
    covered = {id for w in packages for s in w.acceptance if s.status == "confirmed" for id in s.ledger_ids}
    if complete and not required <= covered:
        raise ScopedError("Package acceptance misses confirmed requirements", *(
            locations[w.ref] + ("acceptance",) for w in plan.phases[-1].packages
        ))
    exclusions = {x.id for x in ledger if x.status == "confirmed" and x.type in {"constraint", "non-goal"}}
    producers = {}
    for phase in plan.phases:
        expected = accept_phase(
            PhaseProposal.model_validate(
                phase.model_dump(exclude={"id", "packages"})
                | {
                    "packages": [
                        w.model_dump(exclude={"id", "tasks"})
                        | {"tasks": [t.model_dump(exclude={"id"}) for t in w.tasks]}
                        for w in phase.packages
                    ]
                }
            ),
            plan.outline,
            order[phase.ref],
        )
        if phase != expected:
            raise ValueError("Canonical IDs changed")
    for w in packages:
        for index, path in enumerate(w.owned_paths):
            try:
                safe_path(path)
            except ValueError as error:
                raise ScopedError(str(error), locations[w.ref] + ("owned_paths", index)) from error
        unique([p.casefold() for p in w.owned_paths])
        if not exclusions <= {id for s in w.exclusions for id in s.ledger_ids}:
            raise ScopedError("Package misses scope exclusions", locations[w.ref] + ("exclusions",))
        for dep in reachable[w.ref]:
            if order[owner[dep]] > order[owner[w.ref]]:
                raise ScopedError("Package depends on later phase", locations[w.ref] + ("depends_on",))
            if owner[dep] != owner[w.ref] and owner[dep] not in phase_reachable[owner[w.ref]]:
                raise ScopedError("Package dependency missing from phase graph",
                                  locations[w.ref] + ("depends_on",))
        for interface in w.produces:
            if interface.name in producers:
                raise ValueError("Shared interface has multiple producers")
            producers[interface.name] = (w.ref, interface.version)
    for i, left in enumerate(packages):
        for interface in left.consumes:
            producer = producers.get(interface.name)
            if producer is None or producer[1] != interface.version or producer[0] not in reachable[left.ref]:
                raise ScopedError("Missing or incompatible interface dependency",
                                  locations[left.ref] + ("consumes",))
        for right in packages[i + 1 :]:
            independent = left.ref not in reachable[right.ref] and right.ref not in reachable[left.ref]
            if independent and any(overlaps(a, b) for a in left.owned_paths for b in right.owned_paths):
                raise ValueError("Unordered ownership conflict")
    review_catalog(plan)
    for diagram in [
        plan.outline.architecture,
        *(p.flow for p in plan.phases),
        *(w.flow for w in packages),
        *(x for s in plan.screens for x in s.wireframes.values()),
    ]:
        check_diagram(diagram)
