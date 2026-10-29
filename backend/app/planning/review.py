"""Ephemeral review addresses; saved proposal content and citations stay intact."""

from typing import Literal

from pydantic import BaseModel, Field

from .contracts import PlanningModel, Statement


class ReviewEntry(PlanningModel):
    kind: Literal["statement", "prose"]
    path: list[str | int]
    text: str = Field(min_length=1, max_length=12000)
    ledger_ids: list[str] | None = None
    status: Literal["confirmed", "proposal", "unresolved"] | None = None


# Structural tokens remain in the full plan and under deterministic validation.
STRUCTURAL = {"id", "ref", "depends_on", "produces", "consumes", "command", "states"}
CAPACITY = 500
# Fewest entries a schema-valid phase adds: goal, flow and one minimal package.
MIN_PHASE_ENTRIES = 14


def entries(value, path=()):
    if isinstance(value, Statement):
        yield "S", dict(kind="statement", path=list(path), text=value.text,
                        ledger_ids=value.ledger_ids, status=value.status)
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            if name not in STRUCTURAL:
                yield from entries(getattr(value, name), path + (name,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from entries(item, path + (index,))
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from entries(value[key], path + (key,))
    elif isinstance(value, str):
        yield "F", dict(kind="prose", path=list(path), text=value)


def review_catalog(plan):
    result = {}
    counts = {"S": 0, "F": 0}
    for name in ("outline", "screens", "phases"):
        for prefix, values in entries(getattr(plan, name), (name,)):
            counts[prefix] += 1
            result[f"{prefix}{counts[prefix]}"] = ReviewEntry(**values)
            if len(result) > CAPACITY:
                raise ValueError("Plan exceeds semantic verification capacity")
    return result


def review_count(*values):
    return sum(1 for value in values for _ in entries(value))


def reserved_entries(outline, screens=0, phases=0):
    """Fewest entries the outline's sections after the first screens/phases must still add."""
    # A screen has one purpose and exactly one wireframe per declared state.
    return (sum(1 + len(screen.states) for screen in outline.screens[screens:])
            + MIN_PHASE_ENTRIES * len(outline.phases[phases:]))


def available_entries(accepted, reserved):
    return CAPACITY - review_count(accepted) - reserved


def check_review_budget(accepted, reserved, section):
    """Fail a section before later sections are paid for if the plan can no longer fit review."""
    available = available_entries(accepted, reserved)
    used = review_count(section)
    if used > available:
        raise ValueError(
            f"Section has {used} reviewable text entries; at most {available} fit the "
            f"{CAPACITY}-entry plan review limit with the remaining sections. Return a more "
            "concise complete section: combine or shorten list items without dropping required coverage."
        )


def check_outline_budget(outline):
    check_review_budget([], reserved_entries(outline), outline)
