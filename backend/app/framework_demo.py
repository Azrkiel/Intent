"""Scripted framework illustrations, never live semantic evidence or a fallback."""

from .framework import ASPECTS, FrameworkMap


def demo_framework(session) -> FrameworkMap:
    known = [item.id for item in session.ledger]
    facts = {item.slot: item.text for item in session.ledger if item.status == "confirmed" and item.slot}
    samples = {
        "problem": facts.get("goal", "The user describes the problem to solve."),
        "users": facts.get("access", "The intended user opens the first version."),
        "outcome": facts.get("success-criterion", "The user checks the result of the main action."),
        "entry": "Open the workspace and see an empty state or the current saved records.",
        "actions": facts.get("core-flow", "Enter a record, review its values, and save it."),
        "completion": "Show the resulting record and preserve it using the selected storage policy.",
        "components": "Input controls call a feature handler; a storage adapter reads and writes values.",
        "boundaries": "The view displays state; the feature handler validates changes before storage writes.",
        "dependencies": "The view calls the feature handler, which calls the selected storage adapter.",
        "entities": facts.get("data", "The main record contains the values entered in the core flow."),
        "storage": facts.get("data", "The persistence mechanism remains a user decision."),
        "lifecycle": "Load records on entry; update them on a valid save; delete only on user action.",
        "actors": facts.get("access", "Access remains a user decision."),
        "permissions": facts.get("access", "Only the chosen access policy grants reads or changes."),
        "validation": "A blank required value leaves the form editable and does not write a record.",
        "failure": "A failed save shows an error and preserves the unsaved input.",
        "recovery": "Correct input or explicitly retry the failed action without duplicate records.",
        "observable-behavior": facts.get("success-criterion", "Verify the visible result of the action."),
        "checks": "Exercise the core flow with valid and blank input; simulate a failed save and retry.",
        "included": facts.get("core-flow", "Only the described first-version core flow is included."),
        "excluded": facts.get("non-goals", "Scope exclusions remain a user decision."),
    }
    sections = [
        {"area": area, "entries": [
            {"aspect": aspect, "text": f"Scripted sample: {samples[aspect]}",
             "ledger_ids": known[:1], "status": "proposal"}
            for aspect in aspects
        ]}
        for area, aspects in ASPECTS.items()
    ]
    confirmed = [item for item in session.ledger if item.status == "confirmed"]
    for offset in range(0, len(confirmed), 40):
        group = confirmed[offset:offset + 40]
        sections[0]["entries"].append({
            "aspect": "problem", "status": "confirmed", "ledger_ids": [item.id for item in group],
            "text": "Scripted ledger coverage: " + "; ".join(item.text for item in group)[:1450],
        })
    return FrameworkMap(sections=sections)
