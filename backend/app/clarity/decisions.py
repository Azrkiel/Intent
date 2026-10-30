"""Decisions from candidate divergence; disposition by reversibility; Decision Quality links."""

import math
from collections import Counter
from typing import TYPE_CHECKING

from .contracts import Claim, Decision, DecisionProbe, ProbeAnswer, Scenario, Thresholds

if TYPE_CHECKING:
    from ..domain import AskedQuestion, Session

ONE_WAY = frozenset({"data-model", "identity", "external", "destructive"})
KANO_WEIGHT = {"must-be": 3, "performance": 2, "delighter": 1}
LINKS = ("frame", "alternatives", "information", "values", "reasoning", "commitment")
AGREEMENT = 0.7  # about 70% of the information you wish you had (Bezos, 2016 letter)


def split(votes: list[int]) -> float:
    counts = Counter(votes)
    if len(votes) < 2 or len(counts) == 1:
        return 0.0
    entropy = -sum(c / len(votes) * math.log(c / len(votes)) for c in counts.values())
    return entropy / math.log(min(len(votes), len(counts)))


def majority(votes: list[int]) -> tuple[int, int]:
    counts = Counter(v for v in votes if v >= 0)
    if not counts:
        return -1, 0
    choice = min(counts, key=lambda c: (-counts[c], c))
    return choice, counts[choice]


def delegate(decision: Decision, choice: int) -> None:
    decision.status, decision.owner = "delegated", "delegated"
    decision.outcome = decision.options[max(choice, 0)]
    agreeing = sum(v == max(choice, 0) for v in decision.votes)
    decision.because = (
        f"{decision.drivers[0]}: {agreeing} of {len(decision.votes)} candidate builds chose this"
    )


def dispose(decision: Decision, thresholds: Thresholds) -> None:
    choice, count = majority(decision.votes)
    if decision.reversibility == "one-way":
        decision.status = "open"
    elif count >= math.ceil(AGREEMENT * len(decision.votes)):
        delegate(decision, choice)
    elif decision.kano == "must-be":
        decision.status = "open"
    elif decision.kano == "delighter":
        if choice >= 0:
            delegate(decision, choice)
        else:
            decision.status = "excluded"
            decision.because = f"{decision.drivers[0]}: a nice-to-have nobody needs yet"
    elif decision.due_phase:
        decision.status = "deferred"
    else:
        decision.status = "open"
    # Stop rule (SAGE-Agent): low-value two-way questions become defaults; one-way never stops.
    if (
        decision.status == "open"
        and decision.reversibility == "two-way"
        and decision.score < thresholds.decision_stop
    ):
        delegate(decision, choice)


def build(
    probes: list[DecisionProbe], answers: list[list[ProbeAnswer]], asked: Counter, thresholds: Thresholds
) -> list[Decision]:
    decisions = []
    for probe in probes:
        votes = []
        for builder in answers:
            choice = next((a.choice for a in builder if a.probe_id == probe.id), -1)
            votes.append(choice if choice < len(probe.options) else -1)
        if len(set(votes)) == 1 and votes[0] >= 0:
            continue  # every candidate builds the same thing (ClarifyGPT)
        reversibility = "one-way" if probe.category in ONE_WAY else "two-way"
        spread = split(votes)
        score = spread * KANO_WEIGHT[probe.kano] * (3 if reversibility == "one-way" else 1)
        score -= thresholds.repeat_penalty * asked[probe.category]
        decision = Decision(
            id=f"D-{probe.id}",
            status="open",
            reversibility=reversibility,
            votes=votes,
            split=round(spread, 4),
            score=round(score, 4),
            **probe.model_dump(
                include={
                    "question",
                    "options",
                    "code_diff",
                    "context",
                    "drivers",
                    "kano",
                    "category",
                    "claims",
                    "pros",
                    "cons",
                    "due_phase",
                }
            ),
        )
        dispose(decision, thresholds)
        decisions.append(decision)
    return sorted(decisions, key=lambda d: (-d.score, d.id))


def resolve_vetoes(vetoes: list[Decision], asked: list["AskedQuestion"]) -> list[Decision]:
    answers = {entry.question.id: entry.answer for entry in asked}
    resolved = []
    for veto in vetoes:
        decision = veto.model_copy(deep=True)
        if decision.id in answers:
            decision.status, decision.owner = "decided", "user"
            decision.outcome = answers[decision.id]
            decision.because = f"{decision.drivers[0]}: your answer"
        else:
            decision.status, decision.owner, decision.outcome = "open", None, None
        resolved.append(decision)
    return resolved


def attach_confirmations(decisions: list[Decision], scenarios: list[Scenario]) -> None:
    for decision in decisions:
        decision.confirmation = next((s.id for s in scenarios if set(s.claims) & set(decision.claims)), None)


def quality(decision: Decision, claims: list[Claim], scenarios: list[Scenario]) -> dict[str, bool]:
    claim_ids, scenario_ids = {c.id for c in claims}, {s.id for s in scenarios}
    return {
        "frame": bool(decision.context) and bool(decision.drivers) and set(decision.claims) <= claim_ids,
        "alternatives": len(decision.options) >= 2 and len(decision.code_diff) >= 15,
        "information": len(decision.votes) >= 2,
        "values": decision.because is not None and any(d in decision.because for d in decision.drivers),
        "reasoning": bool(decision.claims),
        "commitment": decision.owner is not None and decision.confirmation in scenario_ids,
    }


def decision_problems(decisions: list[Decision]) -> list[str]:
    problems = []
    for decision in decisions:
        if decision.status == "open":
            problems.append(f"Decide: {decision.question}")
        elif decision.status in ("decided", "delegated"):
            missing = [link for link in LINKS if not decision.quality.get(link)]
            if missing:
                problems.append(
                    f"Complete the decision record for: {decision.question} ({', '.join(missing)})"
                )
            if decision.reversibility == "one-way" and decision.owner != "user":
                problems.append(f"Decide: {decision.question}")
    return problems


def wasted_questions(session: "Session") -> tuple[int, int]:
    """CLAM-style waste: an answer whose turn changed no ledger item."""
    changed = {item.turn for item in session.ledger}
    wasted = sum(entry.turn not in changed for entry in session.questions)
    return wasted, len(session.questions)
