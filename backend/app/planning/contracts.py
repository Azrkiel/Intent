"""Provider proposals are data; only Intent assigns canonical identities/state."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Ref = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,39}$")]
Diagram = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=12000, pattern=r"^[\t\n\r -~]+$"),
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


class PlanningState(PlanningModel):
    status: Literal["draft", "planning", "review_ready", "approved", "blocked", "stale"] = "draft"
    attempts: list[PlanAttempt] = Field(default_factory=list, max_length=2)
    active: PlanApproval | None = None
    approval: PlanApproval | None = None
