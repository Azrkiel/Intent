"""Deterministic claim provenance: computed status, quote tiling, novelty and scenario rules."""

import re
from typing import TYPE_CHECKING

from ..framework import ASPECTS
from .contracts import Claim, ClaimDraft, ClaimMapDraft, ClaimStatus, NotApplicable, Scenario, ScenarioDrafts

if TYPE_CHECKING:
    from ..domain import LedgerItem

STOPWORDS = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are be been being was were "
    "it its this that these those i me my we our you your he she they them their can could should would "
    "will shall may might must do does did so such than too very just also into onto over under up down "
    "out off about after before again there here what which who whom".split()
)
NEGATIONS = frozenset({"no", "not", "never", "without", "none", "nothing", "cannot"})
TOKEN = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?")


def normalize(token: str) -> str:
    token = token.replace("’", "'")
    if token in NEGATIONS or token.endswith("n't"):
        return "not"
    for suffix in ("ing", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    return token[:-1] if token.endswith("e") and len(token) > 3 else token


def content_words(text: str) -> list[str]:
    return [token for token in TOKEN.findall(text.casefold()) if token not in STOPWORDS]


def stems(text: str) -> set[str]:
    return {normalize(word) for word in content_words(text)}


def tag_ok(tag: str) -> bool:
    area, _, aspect = tag.partition("/")
    return area in ASPECTS and aspect in ASPECTS[area]


def novel_words(entry: ClaimDraft) -> list[str]:
    supported = set().union(*(stems(span.quote) for span in entry.spans)) if entry.spans else set()
    return list(dict.fromkeys(w for w in content_words(entry.text) if normalize(w) not in supported))


def computed_status(entry: ClaimDraft, items: dict) -> ClaimStatus:
    grounded = bool(entry.spans) and all(
        span.item_id in items
        and items[span.item_id].status == "confirmed"
        and span.quote in (items[span.item_id].source or "")
        for span in entry.spans
    )
    if entry.basis == "stated" and grounded:
        return "confirmed"
    if entry.basis == "excluded" and grounded:
        return "excluded"
    if entry.basis == "entailed" and entry.premises and entry.derivation:
        return "derived"
    return "proposal"


def build_claims(draft: ClaimMapDraft, ledger: list["LedgerItem"]) -> tuple[list[Claim], list[str]]:
    items = {item.id: item for item in ledger}
    ids = [f"C{index + 1}" for index in range(len(draft.claims))]
    claims, problems = [], []
    for claim_id, entry in zip(ids, draft.claims):
        flags = []
        problems.extend(f"{claim_id} uses unknown tag {tag}." for tag in entry.tags if not tag_ok(tag))
        for span in entry.spans:
            if span.item_id not in items:
                problems.append(f"{claim_id} cites unknown requirement {span.item_id}.")
            elif span.quote not in (items[span.item_id].source or ""):
                problems.append(f'{claim_id} quotes text not in {span.item_id}: "{span.quote}".')
        status = computed_status(entry, items)
        if entry.basis == "stated":
            novel = novel_words(entry)
            if novel:
                flags.append("novel: " + ", ".join(novel))
                status = "proposal"
                problems.append(
                    f"{claim_id} states words its quote does not support: {', '.join(novel)}. "
                    "Split the claim or label that part proposed."
                )
        if entry.basis == "delegated" and entry.reversibility > 1:
            problems.append(f"{claim_id} delegates a choice that is costly to reverse; ask the user.")
        if entry.basis in ("proposed", "delegated") and entry.serves is None:
            problems.append(f"{claim_id} is a proposal that serves no North Star field.")
        claims.append(Claim(**entry.model_dump(), id=claim_id, status=status, flags=flags))
    # Derived claims stand only on confirmed or derived premises.
    by_id = {claim.id: claim for claim in claims}
    for claim in claims:
        if claim.basis != "entailed":
            continue
        premises = [by_id.get(key) for key in claim.premises]
        if (
            not claim.premises
            or not claim.derivation
            or any(p is None or p.status not in ("confirmed", "derived") for p in premises)
        ):
            claim.status = "proposal"
            problems.append(f"{claim.id} needs existing premises and a derivation.")
    return claims, problems


def tiling_gaps(claims: list[Claim], ledger: list["LedgerItem"]) -> dict[str, list[str]]:
    covered: dict[str, set[str]] = {}
    for claim in claims:
        if claim.status in ("confirmed", "excluded"):
            for span in claim.spans:
                covered.setdefault(span.item_id, set()).update(stems(span.quote))
    gaps = {}
    for item in ledger:
        if item.status != "confirmed" or not item.source:
            continue
        missing = [
            word
            for word in dict.fromkeys(content_words(item.source))
            if normalize(word) not in covered.get(item.id, set())
        ]
        if missing:
            gaps[item.id] = missing
    return gaps


def aspect_gaps(
    claims: list[Claim], not_applicable: list[NotApplicable], ledger: list["LedgerItem"]
) -> list[str]:
    confirmed = {item.id for item in ledger if item.status == "confirmed"}
    mapped = {tag for claim in claims for tag in claim.tags}
    exempt = {entry.tag for entry in not_applicable if set(entry.ledger_ids) <= confirmed}
    return [
        f"{area}/{aspect}"
        for area, aspects in ASPECTS.items()
        for aspect in aspects
        if f"{area}/{aspect}" not in mapped | exempt
    ]


def build_scenarios(drafts: ScenarioDrafts, claims: list[Claim]) -> tuple[list[Scenario], list[str]]:
    known = {claim.id for claim in claims}
    scenarios = [
        Scenario(**entry.model_dump(), id=f"S{index + 1}") for index, entry in enumerate(drafts.scenarios)
    ]
    problems = [
        f"{s.id} exercises unknown claim {key}." for s in scenarios for key in s.claims if key not in known
    ]
    exercised = {key for s in scenarios for key in s.claims}
    behavior = [
        claim
        for claim in claims
        if claim.status in ("confirmed", "derived")
        and any(tag.split("/")[0] in ("journeys", "failure-recovery") for tag in claim.tags)
    ]
    problems.extend(f"No scenario exercises {c.id}: {c.text}" for c in behavior if c.id not in exercised)
    excluded = {key for s in scenarios if s.kind == "exclusion" for key in s.claims}
    problems.extend(
        f"No exclusion scenario shows {c.id}: {c.text}"
        for c in claims
        if c.status == "excluded" and c.id not in excluded
    )
    if not any(s.kind == "journey" for s in scenarios):
        problems.append("Add at least one journey scenario.")
    return scenarios, problems
