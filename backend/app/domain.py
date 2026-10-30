from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from .clarity.contracts import ClarityState, Decision
from .discussion.contracts import DiscussionTarget
from .framework import FrameworkReview, framework_blockers, framework_progress, reviewed_context
from .planning.contracts import PlanningState

ItemType = Literal[
    "goal",
    "user",
    "feature",
    "data",
    "constraint",
    "non-goal",
    "decision",
    "assumption",
    "success-criterion",
    "open-question",
]
Status = Literal["confirmed", "inferred", "open", "conflict"]
Slot = Literal["goal", "core-flow", "data", "access", "non-goals", "success-criterion"]
Lens = Literal[
    "data", "identity", "behaviour", "contradictions", "edges", "done-ness", "north-star", "decision"
]
SLOTS = ["goal", "core-flow", "data", "access", "non-goals", "success-criterion"]
LENSES = ["data", "identity", "behaviour", "contradictions", "edges", "done-ness"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftItem(Contract):
    type: ItemType
    text: str = Field(min_length=1, max_length=2000)
    status: Status = "inferred"
    source: str | None = Field(default=None, max_length=6000)
    slot: Slot | None = None


class LedgerItem(DraftItem):
    id: str
    turn: int


class ItemUpdate(Contract):
    id: str
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    status: Status | None = None
    source: str | None = Field(default=None, max_length=6000)
    slot: Slot | None = None


class Delta(Contract):
    add: list[DraftItem] = Field(default_factory=list, max_length=30)
    update: list[ItemUpdate] = Field(default_factory=list, max_length=30)
    answers_question: str | None = None


class Turn(Contract):
    number: int
    text: str
    question_id: str | None = None
    scope: DiscussionTarget | None = Field(default=None, exclude_if=lambda value: value is None)
    suggested: bool = Field(default=False, exclude_if=lambda value: not value)
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Candidate(Contract):
    id: str = ""
    lens: Lens
    targets: list[str] = Field(default_factory=list, max_length=10)
    question: str = Field(min_length=5, max_length=500)
    options: list[str] = Field(min_length=2, max_length=3)
    code_diff: str = Field(min_length=15, max_length=1500)
    divergence: int = Field(ge=1, le=3)
    uncertainty: int = Field(ge=1, le=3)
    cost_to_change: int = Field(ge=1, le=3)
    slot: Slot | None = None
    suggestion: bool = Field(default=False, exclude_if=lambda value: not value)

    @field_validator("options")
    @classmethod
    def distinct_options(cls, value):
        if any(not item.strip() or len(item) > 250 for item in value):
            raise ValueError("Options must be nonempty and at most 250 characters")
        if len({item.strip().casefold() for item in value}) != len(value):
            raise ValueError("Options must be distinct")
        return value

    @computed_field
    @property
    def impact(self) -> int:
        return self.divergence * self.uncertainty * self.cost_to_change


class Critique(Contract):
    candidates: list[Candidate] = Field(default_factory=list, max_length=3)


class AskedQuestion(Contract):
    question: Candidate
    answer: str
    turn: int


class RankScore(Contract):
    id: str
    divergence: int = Field(ge=1, le=3)
    uncertainty: int = Field(ge=1, le=3)
    cost_to_change: int = Field(ge=1, le=3)


class Ranking(Contract):
    scores: list[RankScore] = Field(default_factory=list, max_length=18)


class Playback(Contract):
    sentences: list[str] = Field(min_length=1, max_length=3)


class BriefLine(Contract):
    section: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=3000)
    ledger_ids: list[str] = Field(min_length=1, max_length=40)


class Brief(Contract):
    lines: list[BriefLine] = Field(default_factory=list, max_length=150)
    framework_lines: list[BriefLine] = Field(default_factory=list, max_length=200)

    @computed_field
    @property
    def markdown(self) -> str:
        sections: dict[str, list[str]] = {}
        for line in [*self.lines, *self.framework_lines]:
            section = " ".join(line.section.split())
            text = " ".join(line.text.split())
            sections.setdefault(section, []).append(f"- {text} [{', '.join(line.ledger_ids)}]")
        return (
            "# Build brief\n\n"
            + "\n\n".join(f"## {section}\n" + "\n".join(lines) for section, lines in sections.items())
            + "\n"
        )


class Verification(Contract):
    rejected_line_indices: list[int] = Field(default_factory=list)
    missing_ledger_ids: list[str] = Field(default_factory=list)


class Usage(Contract):
    role: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_usd: float
    latency_ms: int


class Build(Contract):
    status: Literal["idle", "running", "complete", "failed"] = "idle"
    logs: list[str] = Field(default_factory=list)
    directory: str | None = None
    preview_url: str | None = None
    demo: bool = False


class Session(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()))
    mode: Literal["demo", "live"] = "demo"
    title: str = "Untitled idea"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revision: int = 0
    extracted_revision: int = 0
    ledger: list[LedgerItem] = Field(default_factory=list)
    turns: list[Turn] = Field(default_factory=list)
    questions: list[AskedQuestion] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    rejected_candidates: list[Candidate] = Field(default_factory=list)
    current_question: Candidate | None = None
    analysis_complete: bool = False
    framework_review: FrameworkReview | None = None
    clarity_version: int = Field(default=1, ge=1, le=2)
    clarity: ClarityState | None = None
    readbacks: dict[str, str] = Field(default_factory=dict)
    vetoes: list[Decision] = Field(default_factory=list, max_length=12)
    playback: Playback | None = None
    playback_revision: int | None = None
    approved_revision: int | None = None
    brief: Brief | None = None
    compiler_calls: int = 0
    warnings: list[str] = Field(default_factory=list)
    usage: list[Usage] = Field(default_factory=list)
    build: Build = Field(default_factory=Build)
    planning: PlanningState = Field(default_factory=PlanningState)

    @model_validator(mode="after")
    def extension_session_binding(self):
        for field in ("extension", "requalification", "fifth_attempt", "sixth_attempt"):
            grant = getattr(self.planning, field)
            if grant and grant.session_id != self.id:
                raise ValueError(f"Planning {field} belongs to a different session")
        return self


class Gate(Contract):
    ready: bool
    percent: int
    filled: list[str]
    missing: list[str]
    blockers: list[str]


def apply_delta(session: Session, delta: Delta, turn_number: int) -> None:
    """Apply atomically; only exact quotes from this user turn confer confirmation."""
    words = next(turn.text for turn in session.turns if turn.number == turn_number)
    items = {item.id: item.model_copy(deep=True) for item in session.ledger}
    for update in delta.update:
        if update.id not in items:
            raise ValueError(f"Unknown ledger id: {update.id}")
        item = items[update.id]
        data = update.model_dump(exclude_unset=True, exclude={"id"})
        # Changing a meaning or status needs fresh evidence. Unchanged items retain history.
        if "text" in data or "status" in data or "source" in data:
            data["source"] = update.source if update.source and update.source in words else None
            data["turn"] = turn_number
            status = data.get("status") or item.status
            data["status"] = "inferred" if status == "confirmed" and not data["source"] else status
        items[update.id] = LedgerItem.model_validate({**item.model_dump(), **data})
    next_id = max([int(item.id[1:]) for item in session.ledger] or [0]) + 1
    for draft in delta.add:
        if any(
            item.text.casefold() == draft.text.casefold() and item.type == draft.type
            for item in items.values()
        ):
            continue
        source = draft.source if draft.source and draft.source in words else None
        status = "inferred" if draft.status == "confirmed" and not source else draft.status
        item = LedgerItem(
            **{**draft.model_dump(), "source": source, "status": status}, id=f"L{next_id}", turn=turn_number
        )
        items[item.id] = item
        next_id += 1
    session.ledger = list(items.values())


def rank_candidates(candidates: list[Candidate], asked: list[AskedQuestion] | None = None) -> list[Candidate]:
    seen = {q.question.question.strip().casefold() for q in asked or []}
    kept = []
    for candidate in sorted(
        candidates, key=lambda item: (-item.impact, item.lens != "contradictions", item.question.casefold())
    ):
        key = candidate.question.strip().casefold()
        if candidate.divergence <= 1 or key in seen:
            continue
        seen.add(key)
        kept.append(candidate)
    return kept


def gate_for(session: Session) -> Gate:
    filled = [
        slot
        for slot in SLOTS
        if any(item.slot == slot and item.status == "confirmed" and item.source for item in session.ledger)
    ]
    missing = [slot for slot in SLOTS if slot not in filled]
    blockers = [f"Clarify: {q.question}" for q in session.candidates if q.impact >= 12]
    blockers.extend(f"Resolve conflict: {item.text}" for item in session.ledger if item.status == "conflict")
    if session.clarity_version == 2:
        from .clarity.gate import clarity_blockers

        blockers.extend(clarity_blockers(session))
    else:
        blockers.extend(framework_blockers(session))
    if not session.analysis_complete:
        blockers.append("All six lenses must finish before building.")
    ready = not missing and not blockers
    if session.clarity_version == 2:
        from .clarity.gate import clarity_progress

        progress = len(filled) / 6 * 30 + clarity_progress(session) * 65
    elif session.mode == "live" or session.framework_review:
        progress = len(filled) / 6 * 45 + framework_progress(session) * 40
        if session.framework_review and not framework_blockers(session):
            progress += 15
    else:
        progress = len(filled) / 6 * 85
    return Gate(
        ready=ready,
        percent=100 if ready else min(95, round(progress)),
        filled=filled,
        missing=missing,
        blockers=blockers,
    )


def trace_brief(session: Session, brief: Brief, rejected: list[int] | None = None) -> Brief:
    """Structural checks backstop the semantic verifier; fill omissions from the ledger verbatim."""
    items = {item.id: item for item in session.ledger}
    lines = []
    for index, line in enumerate(brief.lines):
        if index in (rejected or []):
            continue
        if any(id not in items for id in line.ledger_ids):
            continue
        if any(items[id].status != "confirmed" for id in line.ledger_ids):
            continue
        lines.append(line)
    covered = {id for line in lines for id in line.ledger_ids}
    sections = {
        "goal": "Goal",
        "user": "Users",
        "feature": "Must have",
        "data": "Data",
        "non-goal": "Must NOT have",
        "constraint": "Constraints",
        "decision": "Decisions",
        "success-criterion": "Done when",
    }
    for item in session.ledger:
        if item.id in covered:
            continue
        if item.status == "confirmed":
            lines.append(
                BriefLine(section=sections.get(item.type, "Decisions"), text=item.text, ledger_ids=[item.id])
            )
        else:
            lines.append(
                BriefLine(
                    section="Undecided",
                    ledger_ids=[item.id],
                    text=f"{item.text} — Undecided: choose the simplest option "
                    "and list the choice in your final summary.",
                )
            )
    framework_lines = []
    if session.clarity_version == 2:
        from .clarity.gate import brief_lines

        framework_lines = brief_lines(session)
    else:
        review = reviewed_context(session)
        if review:
            for section in session.framework_review.framework.sections:
                for entry in section.entries:
                    label = "confirmed" if entry.status == "confirmed" else "proposal"
                    framework_lines.append(BriefLine(
                        section=f"Framework {label}: {section.area}",
                        text=f"{entry.aspect}: {entry.text}", ledger_ids=entry.ledger_ids,
                    ))
    return Brief(lines=lines, framework_lines=framework_lines)


def public_session(session: Session) -> dict:
    from .clarity.gate import readout

    return {
        **session.model_dump(
            mode="json",
            exclude={"planning": {"extension", "requalification", "fifth_attempt", "sixth_attempt"}}
        ),
        "gate": gate_for(session).model_dump(),
        "clarity_readout": readout(session) if session.clarity_version == 2 else None,
        "estimated_usd": round(sum(item.estimated_usd for item in session.usage), 6),
    }
