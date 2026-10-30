"""Scripted clarity responses for demo sessions; never live semantic evidence or a fallback."""

import re

from .clarity.canary import INVENTED, NEGATION, SCOPE_CREEP, VAGUE
from .clarity.contracts import (
    NORTH_STAR_FIELDS,
    PROMPT_ONCE_RULES,
    RUBRIC,
    Alignment,
    Answers,
    ClaimDraft,
    ClaimMapDraft,
    ClaimReview,
    DecisionProbe,
    DecisionProbes,
    Entailment,
    FieldJudgement,
    FieldQuotes,
    FlagRuling,
    NorthStarDraft,
    NorthStarProbes,
    NotApplicable,
    Probe,
    ProbeAnswer,
    ProbeSet,
    ReviewFinding,
    RoundTrip,
    RubricJudgement,
    RuleVerdict,
    ScenarioDraft,
    ScenarioDrafts,
    Span,
    Suggestions,
)
from .clarity.northstar import KEEP, OWN
from .framework import ASPECTS

SLOT_TAGS = {
    "goal": "purpose/problem",
    "core-flow": "journeys/actions",
    "data": "data/storage",
    "access": "access/actors",
    "non-goals": "scope/excluded",
    "success-criterion": "verification/observable-behavior",
}


# Scripted drafts for the propose-and-confirm follow-ups: (drafts, assumptions) per North Star field.
FIELD_DRAFTS = {
    "who-when": (
        ["Just me, on my laptop or phone, once a day", "Me and two friends, on our phones, every week"],
        ["Scripted assumption: one person uses it on a personal device"],
    ),
    "job": (
        ["Track whether I did the thing today", "Keep a record of what I finished each day"],
        ["Scripted assumption: one main job for the first version"],
    ),
    "ambition": (
        ["A personal tool only I use, for months", "Shared with two friends for a year"],
        ["Scripted assumption: no public launch planned"],
    ),
    "today": (
        ["I keep notes in a phone app and lose track of them", "I rely on memory and forget most days"],
        ["Scripted assumption: nothing purpose-built is in use today"],
    ),
    "good": (
        ["I finish the daily check in under a minute", "I see my last 30 days in one glance"],
        ["Scripted assumption: speed matters more than extra features"],
    ),
    "fails-if": (
        ["If an entry I saved is gone after I reload the page", "If I cannot tell what I already did today"],
        ["Scripted assumption: losing saved data is the worst failure"],
    ),
}


def _first_clause(text):
    clause = re.split(r"[.!?;,]", text, maxsplit=1)[0].strip()
    return clause[:200] or text.strip()[:200]


def _field_quotes(session, field):
    """Distinct per field: the job comes from the opening request, the rest from the user's own answers."""
    prefix = f"NS-{field}-"
    answers = [
        entry.answer.strip()
        for entry in session.questions
        if entry.question.id.startswith(prefix) and entry.answer.strip() not in (KEEP, OWN)
    ]
    if field == "job" and session.turns:
        return [_first_clause(session.turns[0].text), *answers]
    return answers


def demo_clarity(session, role, payload):
    if role == "clarity:north-star":
        return NorthStarDraft(
            fields=[FieldQuotes(field=f, quotes=_field_quotes(session, f)) for f in NORTH_STAR_FIELDS]
        )
    if role == "clarity:rubric":
        return RubricJudgement(
            fields=[
                FieldJudgement(
                    field=entry["field"],
                    readback=f"Scripted read-back: {entry['text'][:200]}",
                    verdicts=[
                        RuleVerdict(rule=rule, passed=True, reason="Scripted pass")
                        for rule in (*RUBRIC[entry["field"]], *PROMPT_ONCE_RULES.get(entry["field"], ()))
                    ],
                    flag_rulings=[
                        FlagRuling(word=word, prompt=False, reason="Scripted ruling")
                        for word in entry["flags"]
                    ],
                )
                for entry in payload["fields"]
            ]
        )
    if role == "clarity:probes":
        return NorthStarProbes(
            sets=[
                ProbeSet(
                    field=entry["field"],
                    probes=[
                        Probe(id=f"p{i}", question=f"Scripted probe {i}?", options=["Yes", "No"])
                        for i in range(1, 7)
                    ],
                )
                for entry in payload["fields"]
            ]
        )
    if role.startswith("clarity:candidate:"):
        # Four scripted candidate builds disagree on every probe, so each surfaces as a decision.
        choice = 0 if int(role.rsplit(":", 1)[1]) <= 2 else 1
        return Answers(answers=[ProbeAnswer(probe_id=q["id"], choice=choice) for q in payload["probes"]])
    if role.startswith("clarity:reader:"):
        questions = [q for entry in payload.get("fields", []) for q in entry["questions"]] or payload.get(
            "probes", []
        )
        return Answers(answers=[ProbeAnswer(probe_id=q["id"], choice=0) for q in questions])
    if role == "clarity:suggest":
        drafts, assumed = FIELD_DRAFTS[payload["field"]]
        if payload.get("keep"):
            drafts = [f"{payload['keep']}; {draft[0].lower()}{draft[1:]}" for draft in drafts]
        return Suggestions(drafts=drafts, assumed=assumed)
    if role == "clarity:claims":
        confirmed = [item for item in session.ledger if item.status == "confirmed" and item.source]
        claims = [
            ClaimDraft(
                text=item.source,
                tags=[SLOT_TAGS.get(item.slot, "journeys/actions")],
                basis="excluded" if item.slot == "non-goals" or item.type == "non-goal" else "stated",
                spans=[Span(item_id=item.id, quote=item.source)],
            )
            for item in confirmed
        ]
        used = {claim.tags[0] for claim in claims}
        cite = [confirmed[0].id] if confirmed else []
        return ClaimMapDraft(
            claims=claims,
            not_applicable=[
                NotApplicable(tag=f"{area}/{aspect}", reason="Scripted sample", ledger_ids=cite)
                for area, aspects in ASPECTS.items()
                for aspect in aspects
                if f"{area}/{aspect}" not in used and cite
            ],
        )
    if role == "clarity:scenarios":
        claims = payload["claims"]
        journey = [c["id"] for c in claims if c["tags"][0].split("/")[0] in ("journeys", "failure-recovery")]
        excluded = [c["id"] for c in claims if c["status"] == "excluded"]
        scenarios = [
            ScenarioDraft(
                title="Scripted journey",
                given="the app is open",
                when="the main action runs",
                then="the confirmed result is visible",
                claims=journey or [claims[0]["id"]],
                kind="journey",
            )
        ]
        if excluded:
            scenarios.append(
                ScenarioDraft(
                    title="Scripted exclusion",
                    given="a request for an excluded feature",
                    when="the user looks for it",
                    then="it is not offered",
                    claims=excluded,
                    kind="exclusion",
                )
            )
        return ScenarioDrafts(scenarios=scenarios)
    if role == "clarity:decision-probes":
        if not payload["claims"]:
            return DecisionProbes()
        areas = ("journeys", "failure-recovery")
        journey = [c["id"] for c in payload["claims"] if c["tags"][0].split("/")[0] in areas]
        cites = (journey or [payload["claims"][0]["id"]])[:8]
        return DecisionProbes(
            probes=[
                DecisionProbe(
                    id="data",
                    question="Should your information stay on this device, or be stored on a server?",
                    options=["Keep it on this device only", "Store it on a server so it follows me"],
                    code_diff="Browser storage only versus a server database, sync routes and hosting.",
                    context="Where saved information lives",
                    drivers=["who-when", "ambition"],
                    kano="must-be",
                    category="data-model",
                    claims=cites,
                    pros=["Scripted example of a one-way choice"],
                ),
                DecisionProbe(
                    id="scope",
                    question="Should the first version leave out accounts, payments and sharing?",
                    options=["Leave them out of the first version", "Include one from the start"],
                    code_diff="No auth, billing or sharing code versus sign-in, payments and invites.",
                    context="What the first version excludes",
                    drivers=["ambition", "job"],
                    kano="must-be",
                    category="identity",
                    claims=cites,
                    pros=["Scripted example of a scope choice"],
                ),
            ]
        )
    if role == "clarity:review":
        # Scripted reviewer: recognizes the application's own mutation catalogue. Demo only.
        ledger = {item["id"]: item for item in payload["ledger"]}
        findings = []
        for claim in payload["claims"]:
            text = claim["text"]
            miscited = any(
                span["quote"] not in (ledger.get(span["item_id"], {}).get("source") or "")
                for span in claim["spans"]
            )
            if (
                text in (VAGUE, SCOPE_CREEP)
                or text.startswith(NEGATION)
                or any(text.endswith(extra) for extra in INVENTED)
                or miscited
            ):
                findings.append(ReviewFinding(claim_id=claim["id"], kind="other", detail="Scripted catch"))
        # A quote represents every item whose source contains it, so a miscited claim
        # still represents its true item; only a dropped claim leaves an item uncovered.
        quotes = [span["quote"] for claim in payload["claims"] for span in claim["spans"]]
        omitted = [
            key
            for key, item in ledger.items()
            if item["status"] == "confirmed"
            and item["source"]
            and not any(quote in item["source"] for quote in quotes)
        ]
        return ClaimReview(findings=findings, omitted_ledger_ids=omitted)
    if role == "clarity:entailment":
        return Entailment(verdicts=[{"claim_id": c["claim_id"], "entailed": True} for c in payload["claims"]])
    if role == "clarity:roundtrip":
        return RoundTrip(requirements=payload["claims"][:60])
    if role == "clarity:align":
        return Alignment()
    raise ValueError(f"Unknown demo role: {role}")
