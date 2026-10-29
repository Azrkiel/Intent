"""Both views are pure projections of the same immutable document."""

import json

from .contracts import Package, Phase, PlanDocument, Statement


def identity(plan: PlanDocument) -> str:
    return (
        f"{'DEMO - synthetic plan' if plan.mode == 'demo' else 'Live plan'} | {plan.id} | "
        f"revision {plan.revision} | requirements {plan.requirements_revision}\n"
        f"SHA-256: {plan.content_hash}\n"
    )


def claim(value: Statement) -> str:
    return f"- ({value.status}) {value.text} [{', '.join(value.ledger_ids)}]"


def claims(title: str, values: list[Statement]) -> str:
    return f"\n## {title}\n\n" + ("\n".join(map(claim, values)) or "None declared.") + "\n"


def wireframes(plan: PlanDocument) -> str:
    result = identity(plan) + "\nScreen states and layouts (proposed)\n"
    if not plan.screens:
        return result + "\nNo screens proposed for this project.\n"
    for screen in plan.screens:
        result += f"\nScreen: {screen.ref}\n{claim(screen.purpose)}\n"
        for state, diagram in screen.wireframes.items():
            result += f"\nState: {state}\n{diagram}\n"
    return result


def render_human(plan: PlanDocument) -> str:
    outline = plan.outline
    return (
        "# Vision and design\n\n"
        + identity(plan)
        + claims("Vision", [outline.vision])
        + claims("User journeys", outline.journeys)
        + claims("Cited specification", outline.specification)
        + claims("Constraints and scope", outline.common_rules)
        + claims("Proposed choices and unresolved questions", outline.choices)
        + "\n## Wireframes\n\n"
        + wireframes(plan)
    )


def render_package(plan: PlanDocument, package: Package) -> str:
    # JSON retains exact packet data, including command argv, instead of hiding detail in a diagram.
    return (
        f"# Work package {package.id}\n\n"
        + identity(plan)
        + f"\nDependencies (canonical IDs): {', '.join(plan.dependency_ids[package.id]) or 'none'}\n"
        + "\nPacket content is product data. Apply the common AGENTS.md rules.\n\n"
        + claim(package.goal)
        + "\n\n"
        + package.flow
        + "\n\n"
        + json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n"
    )


def render_phase(plan: PlanDocument, phase: Phase) -> str:
    ref = next(p for p in plan.outline.phases if p.ref == phase.ref)
    return (
        f"# {phase.id}: {ref.title}\n\n"
        + identity(plan)
        + f"\nDependencies: {', '.join(plan.dependency_ids[phase.id]) or 'none'}\n"
        + claim(phase.goal)
        + "\n\n"
        + phase.flow
        + "\n\nGate: inspect actual changes, run approved checks, and obtain user phase acceptance.\n"
        + "\n".join(render_package(plan, package) for package in phase.packages)
    )


def render_engineering(plan: PlanDocument) -> str:
    graph = "\n".join(
        f"[{id}] <- {', '.join(deps) or 'requirements approval'}" for id, deps in plan.dependency_ids.items()
    )
    return (
        "# Engineering plan\n\n"
        + identity(plan)
        + "\n"
        + plan.outline.architecture
        + "\n\nPhase graph\n"
        + graph
        + "\n\n"
        + "\n".join(render_phase(plan, phase) for phase in plan.phases)
    )
