"""Planted-defect calibration: an empty review must be earned (mutation testing of the reviewer)."""

import hashlib
import random
from collections import Counter

from .contracts import Canary, Claim, ClaimReview, ReviewState, Thresholds

INVENTED = (
    "It also asks for confirmation in a dialog first.",
    "It also emails a weekly summary.",
    "It also keeps a backup copy on a server.",
)
SCOPE_CREEP = "Add accounts and cloud sync so the list follows the user to every device."
VAGUE = "It handles this part appropriately and works well."
NEGATION = "It must not be true that "
COST = {"invented": 2, "negated": 3, "miscited": 2, "scope-creep": 3, "omitted": 3, "vague": 1}


def plant(
    claims: list[Claim], ledger_ids: list[str], seed: str
) -> tuple[list[Claim], list[Canary], dict[str, str]]:
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16))
    stated = [c for c in claims if c.status == "confirmed"]
    copy = [c.model_copy(deep=True) for c in claims]
    by_id = {c.id: c for c in copy}
    planted: list[tuple[str, str]] = []
    picks = rng.sample(stated, k=min(4, len(stated)))
    for claim, kind in zip(picks, ("invented", "negated", "miscited", "vague")):
        target = by_id[claim.id]
        if kind == "invented":
            target.text = f"{target.text} {rng.choice(INVENTED)}"
        elif kind == "negated":
            target.text = NEGATION + target.text[0].lower() + target.text[1:]
        elif kind == "miscited":
            others = [key for key in ledger_ids if key not in {s.item_id for s in target.spans}]
            if not others:
                continue
            target.spans = [s.model_copy(update={"item_id": rng.choice(others)}) for s in target.spans]
        else:
            target.text = VAGUE
        planted.append((claim.id, kind))
    creep = Claim(
        id="C-new",
        text=SCOPE_CREEP,
        tags=["scope/included"],
        basis="proposed",
        serves="good",
        reversibility=3,
        status="proposal",
    )
    copy.insert(rng.randrange(len(copy) + 1), creep)
    planted.append(("C-new", "scope-creep"))
    cited = Counter(
        s.item_id for c in claims if c.status == "confirmed" for s in {x.item_id: x for x in c.spans}.values()
    )
    sole = [c for c in stated if c not in picks and c.spans and all(cited[s.item_id] == 1 for s in c.spans)]
    if sole:
        dropped = rng.choice(sole)
        copy = [c for c in copy if c.id != dropped.id]
        planted.append((dropped.spans[0].item_id, "omitted"))
    id_map = {f"R{index + 1}": claim.id for index, claim in enumerate(copy)}
    reverse = {original: renamed for renamed, original in id_map.items()}
    renamed = [
        c.model_copy(update={"id": reverse[c.id], "premises": [reverse.get(p, p) for p in c.premises]})
        for c in copy
    ]
    canaries = [
        Canary(target=key if kind == "omitted" else reverse[key], kind=kind, cost=COST[kind])
        for key, kind in planted
    ]
    return renamed, canaries, id_map


def score(
    review: ClaimReview, canaries: list[Canary], id_map: dict[str, str], thresholds: Thresholds
) -> ReviewState:
    flagged = {f.claim_id for f in review.findings}
    omitted = set(review.omitted_ledger_ids)
    caught = [
        c.target for c in canaries if (c.target in omitted if c.kind == "omitted" else c.target in flagged)
    ]
    critical = [c for c in canaries if c.cost >= 2]
    recall = len(caught) / len(canaries) if canaries else 0.0
    critical_recall = sum(c.target in caught for c in critical) / len(critical) if critical else 0.0
    targets = {c.target for c in canaries}
    return ReviewState(
        canaries=canaries,
        caught=caught,
        recall=round(recall, 4),
        critical_recall=round(critical_recall, 4),
        trusted=bool(canaries)
        and critical_recall >= thresholds.canary_critical_recall
        and recall >= thresholds.canary_overall_recall,
        findings=[
            f.model_copy(update={"claim_id": id_map[f.claim_id]})
            for f in review.findings
            if f.claim_id not in targets and f.claim_id in id_map and id_map[f.claim_id] != "C-new"
        ],
        omitted_ledger_ids=[key for key in review.omitted_ledger_ids if key not in targets],
    )
