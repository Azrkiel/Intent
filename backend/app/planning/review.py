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


def review_catalog(plan):
    entries = {}
    counts = {"S": 0, "F": 0}

    def add(prefix, **values):
        counts[prefix] += 1
        entries[f"{prefix}{counts[prefix]}"] = ReviewEntry(**values)
        if len(entries) > 500:
            raise ValueError("Plan exceeds semantic verification capacity")

    def walk(value, path):
        if isinstance(value, Statement):
            add("S", kind="statement", path=list(path), text=value.text,
                ledger_ids=value.ledger_ids, status=value.status)
        elif isinstance(value, BaseModel):
            for name in type(value).model_fields:
                if name not in STRUCTURAL:
                    walk(getattr(value, name), path + (name,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path + (index,))
        elif isinstance(value, dict):
            for key in sorted(value):
                walk(value[key], path + (key,))
        elif isinstance(value, str):
            add("F", kind="prose", path=list(path), text=value)

    for name in ("outline", "screens", "phases"):
        walk(getattr(plan, name), (name,))
    return entries
