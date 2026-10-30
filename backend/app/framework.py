"""Framework proposals and independent reviews; readiness is application-owned."""

import hashlib
import json
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

if TYPE_CHECKING:
    from .domain import Session

Area = Literal[
    "purpose", "journeys", "structure", "data", "access", "failure-recovery", "verification", "scope"
]
ASPECTS: dict[str, tuple[str, ...]] = {
    "purpose": ("problem", "users", "outcome"),
    "journeys": ("entry", "actions", "completion"),
    "structure": ("components", "boundaries", "dependencies"),
    "data": ("entities", "storage", "lifecycle"),
    "access": ("actors", "permissions"),
    "failure-recovery": ("validation", "failure", "recovery"),
    "verification": ("observable-behavior", "checks"),
    "scope": ("included", "excluded"),
}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class FrameworkContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameworkEntry(FrameworkContract):
    aspect: Identifier
    text: Text
    ledger_ids: list[Identifier] = Field(min_length=1, max_length=40)
    status: Literal["confirmed", "proposal", "unresolved"]


class FrameworkSection(FrameworkContract):
    area: Area
    entries: list[FrameworkEntry] = Field(min_length=1, max_length=20)


class FrameworkQuestion(FrameworkContract):
    area: Area
    question: str = Field(min_length=5, max_length=500)
    options: list[str] = Field(min_length=2, max_length=3)
    code_diff: str = Field(min_length=15, max_length=1500)
    targets: list[Identifier] = Field(default_factory=list, max_length=10)

    @field_validator("options")
    @classmethod
    def distinct_options(cls, options):
        if any(not item.strip() or len(item) > 250 for item in options):
            raise ValueError("Options must be nonempty and at most 250 characters")
        if len({item.strip().casefold() for item in options}) != len(options):
            raise ValueError("Options must be distinct")
        return options


class FrameworkMap(FrameworkContract):
    sections: list[FrameworkSection] = Field(min_length=1, max_length=8)
    questions: list[FrameworkQuestion] = Field(default_factory=list, max_length=8)


class FrameworkIssue(FrameworkContract):
    area: Area
    detail: Text


class FrameworkAssessment(FrameworkContract):
    reviewed_entry_ids: list[Identifier] = Field(min_length=1, max_length=160)
    reviewed_areas: list[Area] = Field(min_length=1, max_length=8)
    issues: list[FrameworkIssue] = Field(default_factory=list, max_length=16)
    questions: list[FrameworkQuestion] = Field(default_factory=list, max_length=8)


class FrameworkReview(FrameworkContract):
    revision: int = Field(ge=0)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["demo", "live"]
    framework: FrameworkMap
    assessment: FrameworkAssessment | None = None


def source_hash(session: "Session") -> str:
    # Compilation appends uncited, low-impact questions for the build brief. These
    # are output annotations, not a change to the user's reviewed intent.
    ledger = [
        item.model_dump(mode="json") for item in session.ledger
        if not (item.type == "open-question" and item.status == "open" and not item.source)
    ]
    content = {"revision": session.revision, "mode": session.mode, "ledger": ledger}
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def entry_catalog(framework: FrameworkMap) -> dict[str, FrameworkEntry]:
    return {
        f"{section.area}.{index}": entry
        for section in framework.sections
        for index, entry in enumerate(section.entries)
    }


def validate_evidence(framework: FrameworkMap, session: "Session") -> None:
    areas = [section.area for section in framework.sections]
    if len(set(areas)) != len(areas):
        raise ValueError("Framework contains duplicate areas")
    items = {item.id: item for item in session.ledger}
    for section in framework.sections:
        for entry in section.entries:
            if entry.aspect not in ASPECTS[section.area]:
                raise ValueError(f"Unknown framework aspect: {section.area}/{entry.aspect}")
            if not set(entry.ledger_ids) <= items.keys():
                raise ValueError("Framework cites an unknown requirement")
            if entry.status == "confirmed" and any(
                items[key].status != "confirmed" for key in entry.ledger_ids
            ):
                raise ValueError("Framework presents an unconfirmed requirement as confirmed")
    validate_questions(framework.questions, session)


def validate_questions(questions: list[FrameworkQuestion], session: "Session") -> None:
    known = {item.id for item in session.ledger}
    if any(not set(question.targets) <= known for question in questions):
        raise ValueError("Framework question cites an unknown requirement")


def validate_assessment(assessment: FrameworkAssessment, framework: FrameworkMap, session: "Session"):
    expected = set(entry_catalog(framework))
    if set(assessment.reviewed_entry_ids) != expected or len(assessment.reviewed_entry_ids) != len(expected):
        raise ValueError("Independent framework review must cover every entry exactly once")
    if set(assessment.reviewed_areas) != set(ASPECTS) or len(assessment.reviewed_areas) != len(ASPECTS):
        raise ValueError("Independent framework review must check all eight areas")
    validate_questions(assessment.questions, session)


def missing_coverage(framework: FrameworkMap, session: "Session") -> list[str]:
    missing = []
    for area, aspects in ASPECTS.items():
        entries = [
            entry for section in framework.sections if section.area == area for entry in section.entries
        ]
        mapped = {entry.aspect for entry in entries if entry.status != "unresolved"}
        missing.extend(f"Map {area}: {aspect}." for aspect in aspects if aspect not in mapped)
    covered = {
        key for entry in entry_catalog(framework).values() if entry.status == "confirmed"
        for key in entry.ledger_ids
    }
    missing.extend(
        f"Map confirmed requirement {item.id}: {item.text}"
        for item in session.ledger if item.status == "confirmed" and item.id not in covered
    )
    return missing


def is_current(session: "Session") -> bool:
    review = session.framework_review
    return bool(
        review and review.revision == session.revision and review.mode == session.mode
        and review.source_hash == source_hash(session)
    )


def framework_blockers(session: "Session") -> list[str]:
    review = session.framework_review
    if review is None:
        # Historical scripted fixtures retain their demonstration behavior. Every
        # new interview gets a visible scripted map; live sessions never bypass it.
        return ["Map and independently review the product framework."] if session.mode == "live" else []
    if not is_current(session):
        return ["The framework review is stale. Analyze the current requirements again."]
    try:
        validate_evidence(review.framework, session)
        if review.assessment:
            validate_assessment(review.assessment, review.framework, session)
    except ValueError as error:
        return [str(error)]
    blockers = missing_coverage(review.framework, session)
    questions = list(review.framework.questions)
    if review.assessment is None:
        blockers.append("Complete the independent framework review.")
    else:
        blockers.extend(f"Review {issue.area}: {issue.detail}" for issue in review.assessment.issues)
        questions.extend(review.assessment.questions)
    blockers.extend(f"Clarify framework: {question.question}" for question in questions)
    return list(dict.fromkeys(blockers))


def framework_progress(session: "Session") -> float:
    if not is_current(session):
        return 0
    mapped = {
        (section.area, entry.aspect)
        for section in session.framework_review.framework.sections
        for entry in section.entries if entry.status != "unresolved"
    }
    expected = {(area, aspect) for area, aspects in ASPECTS.items() for aspect in aspects}
    return len(mapped & expected) / len(expected)


def reviewed_context(session: "Session") -> dict | None:
    if session.clarity_version == 2:
        from .clarity.gate import reviewed_clarity

        return reviewed_clarity(session)
    if not is_current(session) or framework_blockers(session):
        return None
    return session.framework_review.model_dump(mode="json")
