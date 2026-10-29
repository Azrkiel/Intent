"""Provider proposals are data; only Intent assigns canonical identities/state."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Ref = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,39}$")]
Diagram = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=12000,
        pattern=r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]+$",
    ),
]
Texts = Annotated[list[Text], Field(max_length=20)]


class PlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Statement(PlanningModel):
    text: Text
    ledger_ids: list[Text] = Field(min_length=1, max_length=100)
    status: Literal["confirmed", "proposal", "unresolved"] = "proposal"


class SectionRef(PlanningModel):
    ref: Ref
    title: Text
    depends_on: list[Ref] = Field(default_factory=list, max_length=8)


class ScreenRef(PlanningModel):
    ref: Ref
    title: Text
    states: list[Literal["empty", "loading", "error", "success"]] = Field(min_length=1, max_length=4)


class OutlineProposal(PlanningModel):
    vision: Statement
    journeys: list[Statement] = Field(min_length=1, max_length=10)
    specification: list[Statement] = Field(min_length=1, max_length=100)
    common_rules: list[Statement] = Field(max_length=40)
    choices: list[Statement] = Field(max_length=20)
    architecture: Diagram
    screens: list[ScreenRef] = Field(max_length=3)
    phases: list[SectionRef] = Field(min_length=1, max_length=4)


class ScreenProposal(PlanningModel):
    ref: Ref
    purpose: Statement
    wireframes: dict[Literal["empty", "loading", "error", "success"], Diagram] = Field(
        min_length=1, max_length=4
    )


class Check(PlanningModel):
    command: list[Text] = Field(min_length=1, max_length=20)
    expected: Text


class LeafTaskProposal(PlanningModel):
    title: Text
    steps: list[Text] = Field(min_length=1, max_length=12)
    acceptance: list[Statement] = Field(min_length=1, max_length=10)
    checks: list[Check] = Field(min_length=1, max_length=6)


class Interface(PlanningModel):
    name: Ref
    version: Text


class PackageProposal(PlanningModel):
    ref: Ref
    goal: Statement
    depends_on: list[Ref] = Field(max_length=8)
    owned_paths: list[Text] = Field(min_length=1, max_length=20)
    produces: list[Interface] = Field(max_length=10)
    consumes: list[Interface] = Field(max_length=10)
    preconditions: list[Text] = Field(min_length=1, max_length=12)
    inputs: list[Text] = Field(min_length=1, max_length=12)
    outputs: list[Text] = Field(min_length=1, max_length=12)
    flow: Diagram
    tasks: list[LeafTaskProposal] = Field(min_length=1, max_length=3)
    acceptance: list[Statement] = Field(min_length=1, max_length=20)
    exclusions: list[Statement] = Field(max_length=40)
    choices: list[Statement] = Field(max_length=20)
    artifacts: list[Text] = Field(min_length=1, max_length=12)


class PhaseProposal(PlanningModel):
    ref: Ref
    goal: Statement
    flow: Diagram
    packages: list[PackageProposal] = Field(min_length=1, max_length=2)


class LeafTask(LeafTaskProposal):
    id: Text


class Package(PackageProposal):
    id: Text
    tasks: list[LeafTask] = Field(min_length=1, max_length=3)


class Phase(PhaseProposal):
    id: Text
    packages: list[Package] = Field(min_length=1, max_length=2)


class PlanVerification(PlanningModel):
    reviewed_statement_ids: list[Text] = Field(max_length=500)
    rejected_statement_ids: list[Text] = Field(max_length=500)
    missing_ledger_ids: list[Text] = Field(max_length=100)


class SourceItem(PlanningModel):
    id: Text
    type: Text
    text: str = Field(min_length=1, max_length=2000)
    status: Literal["confirmed", "inferred", "open", "conflict"]
    source: str | None = Field(default=None, max_length=6000)
    turn: int = Field(ge=0)


def content_hash(content: dict) -> str:
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PlanDocument(PlanningModel):
    id: Text
    revision: int = Field(ge=1)
    requirements_revision: int = Field(ge=0)
    mode: Literal["demo", "live"]
    outline: OutlineProposal
    screens: list[ScreenProposal] = Field(max_length=3)
    phases: list[Phase] = Field(max_length=4)
    sources: list[SourceItem] = Field(default_factory=list, max_length=100)

    @computed_field
    @property
    def content_hash(self) -> str:
        return content_hash(self.model_dump(mode="json", round_trip=True))

    @computed_field
    @property
    def dependency_ids(self) -> dict[str, list[str]]:
        phases = {p.ref: f"P{i}" for i, p in enumerate(self.outline.phases, 1)}
        packages = {w.ref: w.id for p in self.phases for w in p.packages}
        return {phases[p.ref]: [phases[ref] for ref in p.depends_on] for p in self.outline.phases} | {
            w.id: [packages[ref] for ref in w.depends_on] for p in self.phases for w in p.packages
        }


class PlanApproval(PlanningModel):
    plan_id: Text
    revision: int = Field(ge=1)
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    requirements_revision: int = Field(ge=0)


class PlanAttempt(PlanningModel):
    plan_id: Text
    revision: int = Field(ge=1)
    requirements_revision: int = Field(ge=0)
    passes: list[Text] = Field(default_factory=list, max_length=9)
    outline: OutlineProposal | None = None
    screens: list[ScreenProposal] = Field(default_factory=list, max_length=3)
    phases: list[Phase] = Field(default_factory=list, max_length=4)
    error: str | None = Field(default=None, max_length=500)


class PlanningExtension(PlanningModel):
    id: Text
    session_id: Text
    requirements_revision: int = Field(ge=0)
    prior_attempt_hashes: list[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]] = Field(
        min_length=2, max_length=2
    )
    recorded_at: AwareDatetime
    reason: Text
    implementation_commit: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    approval_text: Text
    status: Literal["granted", "consumed", "invalidated"] = "granted"


class PlanningRequalification(PlanningExtension):
    prior_attempt_hashes: list[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]] = Field(
        min_length=3, max_length=3
    )
    extension_id: Text
    extension_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class PlanningFifthAttempt(PlanningExtension):
    prior_attempt_hashes: list[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]] = Field(
        min_length=4, max_length=4
    )
    requalification_id: Text
    requalification_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class PlanningSixthAttempt(PlanningExtension):
    prior_attempt_hashes: list[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]] = Field(
        min_length=5, max_length=5
    )
    fifth_attempt_id: Text
    fifth_attempt_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class PlanningState(PlanningModel):
    status: Literal["draft", "planning", "review_ready", "approved", "blocked", "stale"] = "draft"
    attempts: list[PlanAttempt] = Field(default_factory=list, max_length=6)
    extension: PlanningExtension | None = None
    requalification: PlanningRequalification | None = None
    fifth_attempt: PlanningFifthAttempt | None = None
    sixth_attempt: PlanningSixthAttempt | None = None
    active: PlanApproval | None = None
    approval: PlanApproval | None = None

    @model_validator(mode="after")
    def bounded_extension(self):
        grant = self.extension
        if len(self.attempts) > 2 and not grant:
            raise ValueError("A third planning attempt requires an extension")
        if grant:
            if len(self.attempts) < 2 or grant.prior_attempt_hashes != [
                content_hash(x.model_dump(mode="json", round_trip=True)) for x in self.attempts[:2]
            ]:
                raise ValueError("Planning extension prior attempts do not match")
            if (grant.status == "consumed") != (len(self.attempts) >= 3):
                raise ValueError("Planning extension consumption does not match attempts")
            if len(self.attempts) >= 3:
                third = self.attempts[2]
                if (
                    third.revision != 3
                    or third.plan_id != self.attempts[0].plan_id
                    or third.requirements_revision != grant.requirements_revision
                ):
                    raise ValueError("Planning extension third attempt identity does not match")
        qualification = self.requalification
        if len(self.attempts) >= 4 and not qualification:
            raise ValueError("A fourth planning attempt requires requalification")
        if qualification:
            if (
                not grant or grant.status != "consumed" or len(self.attempts) < 3
                or qualification.extension_id != grant.id
                or qualification.extension_hash != content_hash(
                    grant.model_dump(mode="json", round_trip=True)
                )
                or qualification.requirements_revision != self.attempts[2].requirements_revision
                or qualification.prior_attempt_hashes != [
                    content_hash(attempt.model_dump(mode="json", round_trip=True))
                    for attempt in self.attempts[:3]
                ]
            ):
                raise ValueError("Planning requalification history or extension does not match")
            if (qualification.status == "consumed") != (len(self.attempts) >= 4):
                raise ValueError("Planning requalification consumption does not match attempts")
            if len(self.attempts) >= 4:
                fourth = self.attempts[3]
                if (
                    fourth.revision != 4
                    or fourth.plan_id != self.attempts[0].plan_id
                    or fourth.requirements_revision != qualification.requirements_revision
                ):
                    raise ValueError("Planning requalification fourth attempt identity does not match")
        fifth = self.fifth_attempt
        if len(self.attempts) >= 5 and not fifth:
            raise ValueError("A fifth planning attempt requires a separate grant")
        if fifth:
            if (
                not qualification or qualification.status != "consumed" or len(self.attempts) < 4
                or fifth.requalification_id != qualification.id
                or fifth.requalification_hash != content_hash(
                    qualification.model_dump(mode="json", round_trip=True)
                )
                or fifth.requirements_revision != self.attempts[3].requirements_revision
                or fifth.prior_attempt_hashes != [
                    content_hash(attempt.model_dump(mode="json", round_trip=True))
                    for attempt in self.attempts[:4]
                ]
            ):
                raise ValueError("Planning fifth-attempt history or requalification does not match")
            if (fifth.status == "consumed") != (len(self.attempts) >= 5):
                raise ValueError("Planning fifth-attempt consumption does not match attempts")
            if len(self.attempts) >= 5:
                attempt = self.attempts[4]
                if (
                    attempt.revision != 5
                    or attempt.plan_id != self.attempts[0].plan_id
                    or attempt.requirements_revision != fifth.requirements_revision
                ):
                    raise ValueError("Planning fifth-attempt identity does not match")
        sixth = self.sixth_attempt
        if len(self.attempts) == 6 and not sixth:
            raise ValueError("A sixth planning attempt requires a separate grant")
        if sixth:
            if (
                not fifth or fifth.status != "consumed" or len(self.attempts) < 5
                or sixth.fifth_attempt_id != fifth.id
                or sixth.fifth_attempt_hash != content_hash(fifth.model_dump(mode="json", round_trip=True))
                or sixth.requirements_revision != self.attempts[4].requirements_revision
                or sixth.prior_attempt_hashes != [
                    content_hash(attempt.model_dump(mode="json", round_trip=True))
                    for attempt in self.attempts[:5]
                ]
            ):
                raise ValueError("Planning sixth-attempt history or fifth grant does not match")
            if (sixth.status == "consumed") != (len(self.attempts) == 6):
                raise ValueError("Planning sixth-attempt consumption does not match attempts")
            if len(self.attempts) == 6:
                attempt = self.attempts[5]
                if (
                    attempt.revision != 6
                    or attempt.plan_id != self.attempts[0].plan_id
                    or attempt.requirements_revision != sixth.requirements_revision
                ):
                    raise ValueError("Planning sixth-attempt identity does not match")
        return self

    def public(self):
        return self.model_dump(
            mode="json", exclude={"extension", "requalification", "fifth_attempt", "sixth_attempt"}
        )
