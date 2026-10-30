"""Scripted clarity responses for demo sessions; never live semantic evidence or a fallback."""

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
from .framework import ASPECTS

SLOT_TAGS = {
    "goal": "purpose/problem",
    "core-flow": "journeys/actions",
    "data": "data/storage",
    "access": "access/actors",
    "non-goals": "scope/excluded",
    "success-criterion": "verification/observable-behavior",
}


def demo_clarity(session, role, payload):
    first = session.turns[0].text if session.turns else ""
    if role == "clarity:north-star":
        drafted = [turn.text for turn in session.turns if turn.suggested]
        quote = drafted[-1] if drafted else first
        return NorthStarDraft(
            fields=[FieldQuotes(field=f, quotes=[quote]) for f in NORTH_STAR_FIELDS if quote]
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
    if role.startswith("clarity:reader:") or role.startswith("clarity:candidate:"):
        questions = [q for entry in payload.get("fields", []) for q in entry["questions"]] or payload.get(
            "probes", []
        )
        return Answers(answers=[ProbeAnswer(probe_id=q["id"], choice=0) for q in questions])
    if role == "clarity:suggest":
        return Suggestions(
            drafts=[
                "Scripted draft: only me, on my laptop, daily",
                "Scripted draft: me and two friends, weekly",
            ],
            assumed=["Scripted assumption: a laptop browser"],
        )
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
        return DecisionProbes()
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
