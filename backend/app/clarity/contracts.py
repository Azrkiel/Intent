"""Clarity v2 contracts. Models propose drafts; the application computes status and readiness."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ClaimText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
# Options and questions become question cards (domain.Candidate): at most 250 characters, distinct.
Option = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]


def _distinct(value: list[str]) -> list[str]:
    if len({item.casefold() for item in value}) != len(value):
        raise ValueError("Options must be distinct")
    return value


Options = Annotated[list[Option], AfterValidator(_distinct)]

NorthStarField = Literal["who-when", "job", "ambition", "today", "good", "fails-if"]
ReaderVariation = Literal["perspective", "temperature", "tier"]
# Question order: who/job/ambition set proportionality for the rest (spec §2.3).
NORTH_STAR_FIELDS: tuple[str, ...] = ("who-when", "job", "ambition", "today", "good", "fails-if")
FIELD_LABELS = {
    "who-when": "Who & when",
    "job": "Job",
    "ambition": "Ambition",
    "today": "Today",
    "good": "Good looks like",
    "fails-if": "Fails if",
}
RUBRIC: dict[str, tuple[str, ...]] = {
    "who-when": ("W1", "W2", "W3", "W4"),
    "job": ("J1", "J2"),
    "ambition": ("A1", "A2", "A3"),
    "today": ("T1", "T2"),
    "good": ("O1", "O3"),
    "fails-if": ("F1", "F2"),
}
# Prompted once for higher clarity; never blocking by themselves (spec §2.1-2.2).
PROMPT_ONCE_RULES: dict[str, tuple[str, ...]] = {"good": ("O2",)}
RULE_TEXT = {
    "W1": "name a person or group you can identify (\"I\" counts for your own tool), not 'users' or 'people'",
    "W2": "describe the moment that makes them reach for it",
    "W3": "say which device or place they use",
    "W4": "say how often it happens",
    "J1": "use one verb and one object, without 'and' or 'or'",
    "J2": "describe the job without naming a feature or technology",
    "A1": "choose throwaway, personal tool, shared with a few people, or product",
    "A2": "say who else will use it",
    "A3": "say how long it should last",
    "T1": "name how this is done today",
    "T2": "name one concrete pain with today's way",
    "O1": "give a direction, a measure, an object and a context",
    "O2": "put a number with a unit on it",
    "O3": "describe the outcome without naming a feature",
    "F1": "describe a failure you could observe: if something happens, then what you see",
    "F2": "make that failure specific to this product",
}

Basis = Literal["stated", "entailed", "delegated", "proposed", "excluded"]
ClaimStatus = Literal["confirmed", "derived", "proposal", "excluded"]
Kano = Literal["must-be", "performance", "delighter"]
Category = Literal["data-model", "identity", "external", "destructive", "behavior", "presentation", "other"]
ScenarioKind = Literal["journey", "failure", "exclusion"]
FindingKind = Literal["invented", "omitted", "negated", "miscited", "scope-creep", "vague", "other"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Thresholds(Contract):
    alpha_pass: float = Field(default=0.80, ge=0, le=1)
    alpha_floor: float = Field(default=0.667, ge=0, le=1)
    canary_critical_recall: float = Field(default=1.0, ge=0, le=1)
    canary_overall_recall: float = Field(default=0.80, ge=0, le=1)
    decision_stop: float = Field(default=1.5, ge=0, le=9)
    repeat_penalty: float = Field(default=0.5, ge=0, le=9)


# Model outputs: North Star.
class FieldQuotes(Contract):
    field: NorthStarField
    quotes: list[Text] = Field(default_factory=list, max_length=6)


class NorthStarDraft(Contract):
    fields: list[FieldQuotes] = Field(default_factory=list, max_length=6)


class RuleVerdict(Contract):
    rule: Identifier
    passed: bool
    reason: Short
    options: Options = Field(default_factory=list, max_length=3)


class FlagRuling(Contract):
    word: Short
    prompt: bool
    reason: Short
    options: Options = Field(default_factory=list, max_length=3)


class FieldJudgement(Contract):
    field: NorthStarField
    verdicts: list[RuleVerdict] = Field(default_factory=list, max_length=8)
    flag_rulings: list[FlagRuling] = Field(default_factory=list, max_length=12)
    readback: Text


class RubricJudgement(Contract):
    fields: list[FieldJudgement] = Field(default_factory=list, max_length=6)


class Probe(Contract):
    id: Identifier
    question: Short
    options: Options = Field(min_length=2, max_length=4)
    one_way: bool = False


class ProbeSet(Contract):
    field: NorthStarField
    probes: list[Probe] = Field(min_length=6, max_length=8)


class NorthStarProbes(Contract):
    sets: list[ProbeSet] = Field(default_factory=list, max_length=6)


class ProbeAnswer(Contract):
    probe_id: Identifier
    choice: int = Field(ge=-1, le=3)  # -1 means "cannot tell"


class Answers(Contract):
    answers: list[ProbeAnswer] = Field(default_factory=list, max_length=60)


class Suggestions(Contract):
    drafts: Options = Field(min_length=2, max_length=3)
    assumed: list[Short] = Field(default_factory=list, max_length=6)


# Model outputs: claims and scenarios.
class Span(Contract):
    item_id: Identifier
    quote: Text


class ClaimDraft(Contract):
    text: ClaimText
    tags: list[Identifier] = Field(min_length=1, max_length=4)
    basis: Basis
    spans: list[Span] = Field(default_factory=list, max_length=6)
    premises: list[Identifier] = Field(default_factory=list, max_length=6)
    derivation: Short | None = None
    serves: NorthStarField | None = None
    reversibility: int = Field(default=1, ge=1, le=3)


class NotApplicable(Contract):
    tag: Identifier
    reason: Short
    ledger_ids: list[Identifier] = Field(min_length=1, max_length=6)


class ClaimMapDraft(Contract):
    claims: list[ClaimDraft] = Field(min_length=1, max_length=160)
    not_applicable: list[NotApplicable] = Field(default_factory=list, max_length=24)


class ScenarioDraft(Contract):
    title: Short
    given: Text
    when: Text
    then: Text
    claims: list[Identifier] = Field(min_length=1, max_length=12)
    kind: ScenarioKind


class ScenarioDrafts(Contract):
    scenarios: list[ScenarioDraft] = Field(min_length=1, max_length=24)


# Model outputs: decisions.
class DecisionProbe(Contract):
    id: Identifier
    question: Question
    options: Options = Field(min_length=2, max_length=3)
    code_diff: Annotated[str, StringConstraints(strip_whitespace=True, min_length=15, max_length=1500)]
    context: Short
    drivers: list[NorthStarField] = Field(min_length=1, max_length=3)
    kano: Kano
    category: Category
    claims: list[Identifier] = Field(default_factory=list, max_length=8)
    pros: list[Short] = Field(default_factory=list, max_length=3)
    cons: list[Short] = Field(default_factory=list, max_length=3)
    due_phase: Annotated[str, StringConstraints(pattern=r"^P[1-9]$")] | None = None


class DecisionProbes(Contract):
    probes: list[DecisionProbe] = Field(default_factory=list, max_length=12)


# Model outputs: review.
class ReviewFinding(Contract):
    claim_id: Identifier
    kind: FindingKind
    detail: Short


class ClaimReview(Contract):
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=40)
    omitted_ledger_ids: list[Identifier] = Field(default_factory=list, max_length=40)


class EntailmentVerdict(Contract):
    claim_id: Identifier
    entailed: bool
    extra: Short | None = None


class Entailment(Contract):
    verdicts: list[EntailmentVerdict] = Field(default_factory=list, max_length=160)


class RoundTrip(Contract):
    requirements: list[Text] = Field(default_factory=list, max_length=60)


class Alignment(Contract):
    missing_ledger_ids: list[Identifier] = Field(default_factory=list, max_length=60)
    extra_indices: list[int] = Field(default_factory=list, max_length=60)


# Application-owned state.
class LexiconFlag(Contract):
    word: Short
    category: Identifier
    auto: bool


class FieldState(Contract):
    field: NorthStarField
    text: str = ""
    text_hash: str = ""
    flags: list[LexiconFlag] = Field(default_factory=list)
    judgement: FieldJudgement | None = None
    probes: list[Probe] = Field(default_factory=list)
    reader_a: list[ProbeAnswer] = Field(default_factory=list)
    reader_b: list[ProbeAnswer] = Field(default_factory=list)
    alpha: float | None = None
    failing: list[str] = Field(default_factory=list)
    passed: bool = False


class Claim(ClaimDraft):
    id: Identifier
    status: ClaimStatus
    flags: list[str] = Field(default_factory=list)


class Scenario(ScenarioDraft):
    id: Identifier


class Decision(Contract):
    id: Identifier
    status: Literal["open", "decided", "delegated", "deferred", "excluded"]
    question: Short
    options: list[Short] = Field(min_length=2, max_length=3)
    code_diff: str
    context: Short
    drivers: list[NorthStarField] = Field(min_length=1, max_length=3)
    kano: Kano
    category: Category
    reversibility: Literal["one-way", "two-way"]
    claims: list[Identifier] = Field(default_factory=list)
    pros: list[Short] = Field(default_factory=list)
    cons: list[Short] = Field(default_factory=list)
    due_phase: str | None = None
    votes: list[int] = Field(default_factory=list)
    split: float = 0
    score: float = 0
    outcome: str | None = None
    because: str | None = None
    owner: Literal["user", "delegated"] | None = None
    confirmation: Identifier | None = None
    quality: dict[str, bool] = Field(default_factory=dict)


class Canary(Contract):
    target: Identifier  # mutated claim id in the review copy, or a ledger id for an omission
    kind: FindingKind
    cost: int = Field(ge=1, le=3)


class ReviewState(Contract):
    canaries: list[Canary] = Field(default_factory=list)
    caught: list[Identifier] = Field(default_factory=list)
    recall: float = 0
    critical_recall: float = 0
    trusted: bool = False
    findings: list[ReviewFinding] = Field(default_factory=list)
    omitted_ledger_ids: list[Identifier] = Field(default_factory=list)
    entailment_failures: list[Identifier] = Field(default_factory=list)
    roundtrip_missing: list[Identifier] = Field(default_factory=list)


class ClarityState(Contract):
    revision: int = Field(ge=0)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["demo", "live"]
    thresholds: Thresholds = Field(default_factory=Thresholds)
    fields: list[FieldState] = Field(default_factory=list)
    fatigued: bool = False
    suggestions: list[str] = Field(default_factory=list)
    assumed: list[str] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    not_applicable: list[NotApplicable] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    review: ReviewState | None = None
    problems: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    downstream_complete: bool = False
