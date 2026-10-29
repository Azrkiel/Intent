from urllib.parse import quote

from ..planning.contracts import PlanApproval, PlanDocument
from ..planning.render import claim, claims, render_package
from .contracts import Note, Vault


def seed_vault(vault: Vault, plan: PlanDocument, *, partial: bool) -> Vault:
    if vault.source:
        raise ValueError("This vault already contains a plan snapshot. Existing edits are preserved.")
    root = next(n for n in vault.notes if n.id == "plan")
    notes = []

    def link(path, title):
        return f"[{title.replace('[', '').replace(']', '').replace(chr(10), ' ')}]({quote(path, safe='/')})"

    def add(id, path, kind, body):
        notes.append(
            Note(id=id, path=path, kind=kind, body=body + "\n\n" + link(root.path, "Main plan") + "\n")
        )

    add(
        "vision",
        "Vision.md",
        "spec",
        "# Vision\n" + claims("Vision", [plan.outline.vision]) + claims("Journeys", plan.outline.journeys),
    )
    add(
        "specification",
        "Specification.md",
        "spec",
        "# Specification\n"
        + claims("Requirements", plan.outline.specification)
        + claims("Constraints", plan.outline.common_rules)
        + claims("Choices", plan.outline.choices),
    )
    add(
        "architecture",
        "Architecture.md",
        "spec",
        "# Architecture\n\n```text\n" + plan.outline.architecture.replace("```", "~~~") + "\n```\n",
    )
    phase_paths = {p.ref: f"Phase-{i}.md" for i, p in enumerate(plan.outline.phases, 1)}
    package_paths = {w.ref: f"{w.id}.md" for p in plan.phases for w in p.packages}
    for index, ref in enumerate(plan.outline.phases, 1):
        phase = next((p for p in plan.phases if p.ref == ref.ref), None)
        body = f"# {ref.title}\n\n" + (claim(phase.goal) if phase else "Details pending validation.")
        body += "\n\n## Prerequisites\n" + "\n".join(link(phase_paths[d], d) for d in ref.depends_on)
        if phase:
            body += "\n\n## Packages\n" + "\n".join(
                link(package_paths[w.ref], w.goal.text) for w in phase.packages
            )
            for package in phase.packages:
                body_package = render_package(plan, package)
                body_package += "\n## Prerequisites\n" + "\n".join(
                    link(package_paths[d], d) for d in package.depends_on if d in package_paths
                )
                body_package += "\n\n## Tasks\n" + "\n".join(
                    link(f"{t.id}.md", t.title) for t in package.tasks
                )
                add(package.id, package_paths[package.ref], "package", body_package)
                for task in package.tasks:
                    add(
                        task.id,
                        f"{task.id}.md",
                        "task",
                        f"# {task.title}\n\n"
                        + "\n".join(f"{i}. {step}" for i, step in enumerate(task.steps, 1))
                        + claims("Acceptance", task.acceptance)
                        + "\n## Checks (proposed; not executed)\n```json\n"
                        + task.model_dump_json(include={"checks"}, indent=2)
                        + "\n```\n\n"
                        + link(package_paths[package.ref], "Work package"),
                    )
        add(f"phase-{index}", phase_paths[ref.ref], "phase", body)
    for index, screen in enumerate(plan.screens, 1):
        add(
            f"screen-{index}",
            f"Screen-{index}.md",
            "screen",
            f"# {screen.ref}\n\n"
            + claim(screen.purpose)
            + "\n\n"
            + "\n\n".join(
                f"## {state}\n```text\n{diagram.replace('```', '~~~')}\n```"
                for state, diagram in screen.wireframes.items()
            ),
        )
    existing = {n.path.casefold() for n in vault.notes}
    if any(n.path.casefold() in existing or n.id in {x.id for x in vault.notes} for n in notes):
        raise ValueError(
            "A generated note conflicts with an existing note. Rename it before adding the plan."
        )
    provenance = (
        f"\n\n## Plan snapshot\n\n{'DEMO — synthetic plan. ' if plan.mode == 'demo' else ''}"
        f"{'Draft sections; validation pending. ' if partial else 'Validated plan snapshot. '}"
        f"Revision {plan.revision}; requirements {plan.requirements_revision}.\n\n"
        "Editable notes do not change canonical plan approval.\n\n"
    )
    root = root.model_copy(
        update={"body": root.body + provenance + "\n".join(link(n.path, n.path[:-3]) for n in notes) + "\n"}
    )
    return Vault(
        revision=vault.revision,
        demo=vault.demo,
        notes=[root, *[n for n in vault.notes if n.id != "plan"], *notes],
        source=PlanApproval(
            plan_id=plan.id,
            revision=plan.revision,
            content_hash=plan.content_hash,
            requirements_revision=plan.requirements_revision,
        ),
        source_status="draft" if partial else "validated",
    )
