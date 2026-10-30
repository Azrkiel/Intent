"""Clarity v2 readiness, readout, approval and handoff context. Application-owned."""

from ..framework import source_hash
from .contracts import FIELD_LABELS, NORTH_STAR_FIELDS, RULE_TEXT
from .decisions import decision_problems
from .provenance import aspect_gaps, tiling_gaps


def is_current(session) -> bool:
    state = session.clarity
    return bool(
        state
        and state.revision == session.revision
        and state.mode == session.mode
        and state.source_hash == source_hash(session)
    )


def describe(code: str) -> str:
    if code == "missing":
        return "not answered yet"
    if code == "G3":
        return "confirm Intent's read-back"
    if code.startswith("G1:"):
        return f'clarify "{code[3:]}" (or keep your wording)'
    if code.startswith("G4:"):
        return "two independent readers understood this differently"
    if code.startswith("judge:"):
        return f"the rubric judge did not check {code[6:]}; analyze again"
    return RULE_TEXT.get(code, code)


def clarity_blockers(session) -> list[str]:
    state = session.clarity
    if state is None:
        return ["Check the North Star, claims and decisions for this revision."]
    if not is_current(session):
        return ["The clarity review is stale. Analyze the current requirements again."]
    blockers = list(state.failures)
    fields = {f.field: f for f in state.fields}
    for name in NORTH_STAR_FIELDS:
        field = fields.get(name)
        if field is None:
            blockers.append(f"North Star {FIELD_LABELS[name]}: not checked yet")
        elif not field.passed:
            blockers.append(f"North Star {FIELD_LABELS[name]}: {describe(field.failing[0])}")
    if len(blockers) > len(state.failures):
        return list(dict.fromkeys(blockers))
    if not state.downstream_complete:
        blockers.append("Map claims, scenarios and decisions.")
        return list(dict.fromkeys(blockers))
    blockers.extend(state.problems)
    blockers.extend(
        f'Map "{" ".join(words)}" from {key}.'
        for key, words in tiling_gaps(state.claims, session.ledger).items()
    )
    blockers.extend(
        f"Map {tag} or mark it not applicable with a citation."
        for tag in aspect_gaps(state.claims, state.not_applicable, session.ledger)
    )
    blockers.extend(decision_problems(state.decisions))
    review = state.review
    if review is None:
        blockers.append("Complete the calibrated claim review.")
    else:
        if not review.trusted:
            blockers.append(
                f"Framework review could not be verified: it caught {len(review.caught)} "
                f"of {len(review.canaries)} planted defects."
            )
        blockers.extend(f"Review {f.claim_id}: {f.detail}" for f in review.findings)
        blockers.extend(
            f"Review: {key} is not represented by any claim." for key in review.omitted_ledger_ids
        )
        blockers.extend(f"Claim {key} says more than its source." for key in review.entailment_failures)
        blockers.extend(f"Round-trip could not reconstruct {key}." for key in review.roundtrip_missing)
    if not state.scenarios:
        blockers.append("Write scenarios for approval.")
    return list(dict.fromkeys(blockers))


def clarity_progress(session) -> float:
    if not is_current(session):
        return 0
    state = session.clarity
    fields = sum(f.passed for f in state.fields) / len(NORTH_STAR_FIELDS)
    rest = (
        0.5
        if state.downstream_complete and not clarity_blockers(session)
        else 0.25
        if state.downstream_complete
        else 0
    )
    return fields * 0.5 + rest


def readout(session) -> dict | None:
    if not is_current(session):
        return None
    state = session.clarity
    return {
        "statements": sum(c.status in ("confirmed", "excluded") for c in state.claims),
        "unmapped_words": sum(len(w) for w in tiling_gaps(state.claims, session.ledger).values()),
        "choices_made": sum(d.status == "delegated" for d in state.decisions),
        "decisions_open": sum(d.status == "open" for d in state.decisions),
        "scenarios": len(state.scenarios),
    }


def approval_ready(session) -> bool:
    if session.clarity_version == 2:
        return is_current(session) and bool(session.clarity.scenarios)
    return session.playback_revision == session.revision


def reviewed_clarity(session) -> dict | None:
    if not is_current(session) or clarity_blockers(session):
        return None
    state = session.clarity
    return {
        "note": "Claims labeled proposal are reviewed proposals, not user requirements.",
        "north_star": {f.field: f.text for f in state.fields},
        "claims": [
            c.model_dump(mode="json", include={"id", "text", "tags", "status", "spans"}) for c in state.claims
        ],
        "scenarios": [s.model_dump(mode="json") for s in state.scenarios],
        "decisions": [d.model_dump(mode="json") for d in state.decisions if d.status != "open"],
    }


def brief_lines(session) -> list:
    from ..domain import BriefLine

    if reviewed_clarity(session) is None:
        return []
    state = session.clarity
    lines = [
        BriefLine(
            section=f"Clarity {c.status}: {c.tags[0].split('/')[0]}",
            text=c.text,
            ledger_ids=list(dict.fromkeys(s.item_id for s in c.spans)) or [f"NS-{c.serves or 'map'}"],
        )
        for c in state.claims
    ]
    lines.extend(
        BriefLine(
            section="Done when (approved scenarios)",
            text=f"{s.title}: given {s.given}, when {s.when}, then {s.then}",
            ledger_ids=[s.id, *s.claims],
        )
        for s in state.scenarios
    )
    lines.extend(
        BriefLine(
            section="Choices made for you" if d.status == "delegated" else "Decisions",
            text=f"{d.question} -> {d.outcome or d.status} ({d.because or d.due_phase or ''})",
            ledger_ids=[d.id],
        )
        for d in state.decisions
        if d.status != "open"
    )
    return lines[:200]
