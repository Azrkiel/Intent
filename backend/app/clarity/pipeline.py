"""Clarity v2 passes. Models answer narrow questions; the application decides."""

import asyncio
from collections import Counter

from ..framework import ASPECTS, source_hash
from ..models import ModelError
from . import prompts
from .canary import plant, score
from .contracts import (
    FIELD_LABELS,
    NORTH_STAR_FIELDS,
    PROMPT_ONCE_RULES,
    RUBRIC,
    RULE_TEXT,
    Alignment,
    Answers,
    ClaimMapDraft,
    ClaimReview,
    ClarityState,
    DecisionProbes,
    Entailment,
    FieldState,
    NorthStarDraft,
    NorthStarProbes,
    RoundTrip,
    RubricJudgement,
    ScenarioDrafts,
    Suggestions,
    Thresholds,
)
from .decisions import attach_confirmations, quality, settle
from .decisions import build as build_decisions
from .gate import describe
from .lexicon import scan
from .northstar import accept_drafted, evaluate, fatigued, field_texts, follow_up, text_hash
from .provenance import aspect_gaps, build_claims, build_scenarios, tiling_gaps

CANDIDATES = 4


async def gather_all(*calls):
    """asyncio.gather, but a failure cancels the siblings, so none saves after the request lock is gone."""
    tasks = [asyncio.ensure_future(call) for call in calls]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


READER_B = {
    "perspective": ("clarity:reader:b", prompts.READER_SKEPTIC),
    "temperature": ("clarity:reader:b:temperature", prompts.READER),
    "tier": ("clarity:reader:b:tier", prompts.READER),
}


class ClarityPipeline:
    def __init__(self, call, save, thresholds: Thresholds):
        self.call, self.save, self.thresholds = call, save, thresholds

    async def run(self, session, seeds: list[str]):
        state = ClarityState(
            revision=session.revision,
            source_hash=source_hash(session),
            mode=session.mode,
            thresholds=self.thresholds,
            seeds=seeds,
        )
        session.clarity = state
        try:
            await self.north_star(session, state)
        except (ModelError, ValueError) as error:
            state.failures.append(f"north-star: {error}"[:500])
        self.save(session)
        if not state.failures and all(f.passed for f in state.fields):
            await self.downstream(session, state)
            self.save(session)
        return self.questions(session, state)

    async def refresh(self, session):
        state = session.clarity
        self.refresh_fields(session, state)
        if not state.failures and not state.downstream_complete and all(f.passed for f in state.fields):
            await self.downstream(session, state)
        self.save(session)
        return self.questions(session, state)

    def refresh_fields(self, session, state):
        asked = {entry.question.id for entry in session.questions}
        for field in state.fields:
            evaluate(field, asked, session.readbacks, state.thresholds)

    async def north_star(self, session, state):
        user_texts = [turn.text for turn in session.turns]
        draft = await self.call(
            session,
            "clarity:north-star",
            NorthStarDraft,
            prompts.NORTH_STAR,
            {"turns": [{"number": t.number, "text": t.text} for t in session.turns]},
        )
        texts, _ = field_texts(draft, user_texts)  # invalid quotes are dropped, like ledger sources
        state.fields = [
            FieldState(
                field=name,
                text=texts.get(name, ""),
                text_hash=text_hash(texts.get(name, "")),
                flags=scan(texts.get(name, "")),
            )
            for name in NORTH_STAR_FIELDS
        ]
        present = [f for f in state.fields if f.text]
        if present:
            judge_payload = {
                "fields": [
                    {
                        "field": f.field,
                        "text": f.text,
                        "flags": [flag.word for flag in f.flags],
                        "rules": {
                            rule: RULE_TEXT[rule]
                            for rule in (*RUBRIC[f.field], *PROMPT_ONCE_RULES.get(f.field, ()))
                        },
                    }
                    for f in present
                ]
            }
            judgement, probe_sets = await gather_all(
                self.call(session, "clarity:rubric", RubricJudgement, prompts.RUBRIC_JUDGE, judge_payload),
                self.call(
                    session,
                    "clarity:probes",
                    NorthStarProbes,
                    prompts.READER_PROBES,
                    {"fields": [{"field": f.field, "text": f.text} for f in present]},
                ),
            )
            judged = {entry.field: entry for entry in judgement.fields}
            sets = {entry.field: entry.probes for entry in probe_sets.sets}
            for f in present:
                f.judgement = judged.get(f.field)
                f.probes = [
                    p.model_copy(update={"id": f"{f.field}.p{i + 1}"})
                    for i, p in enumerate(sets.get(f.field, []))
                ]
            state.failures.extend(
                f"clarity: reader probes missing for {FIELD_LABELS[f.field]}" for f in present if not f.probes
            )
            reader_payload = {
                "fields": [
                    {
                        "field": f.field,
                        "text": f.text,
                        "questions": [p.model_dump(include={"id", "question", "options"}) for p in f.probes],
                    }
                    for f in present
                ]
            }
            role_b, prompt_b = READER_B[session.clarity_reader_variation]
            first, second = await gather_all(
                self.call(session, "clarity:reader:a", Answers, prompts.READER, reader_payload),
                self.call(session, role_b, Answers, prompt_b, reader_payload),
            )
            for f in present:
                ids = {p.id for p in f.probes}
                f.reader_a = [x for x in first.answers if x.probe_id in ids]
                f.reader_b = [x for x in second.answers if x.probe_id in ids]
        accept_drafted(state.fields, session)
        self.refresh_fields(session, state)
        state.fatigued = fatigued(session)  # recorded for evals; drafting does not wait for fatigue
        target = next((f for f in state.fields if not f.passed and set(f.failing) - {"G3"}), None)
        if target:
            drafts = await self.call(
                session,
                "clarity:suggest",
                Suggestions,
                prompts.SUGGEST,
                {
                    "field": target.field,
                    "label": FIELD_LABELS[target.field],
                    "current": target.text,
                    "failing": [describe(code) for code in target.failing if code != "G3"],
                    "turns": [t.text for t in session.turns],
                },
            )
            screened = [d for d in drafts.drafts if not any(flag.auto for flag in scan(d))]
            state.suggestions = screened if len(screened) >= 2 else []
            state.assumed = list(drafts.assumed) if state.suggestions else []

    async def downstream(self, session, state):
        base = {
            "north_star": {f.field: f.text for f in state.fields},
            "ledger": [item.model_dump(mode="json") for item in session.ledger],
            "turns": [{"number": t.number, "text": t.text} for t in session.turns],
            "required_tags": [f"{area}/{aspect}" for area, aspects in ASPECTS.items() for aspect in aspects],
        }
        try:
            feedback = None
            for attempt in range(2):
                payload = {**base, **({"review_feedback": feedback} if feedback else {})}
                draft = await self.call(session, "clarity:claims", ClaimMapDraft, prompts.CLAIMS, payload)
                claims, problems = build_claims(draft, session.ledger)
                gaps = tiling_gaps(claims, session.ledger)
                tags = aspect_gaps(claims, draft.not_applicable, session.ledger)
                if attempt or not (problems or gaps or tags):
                    break
                feedback = {"problems": problems, "unmapped_words": gaps, "unmapped_tags": tags}
            state.claims, state.not_applicable, state.problems = claims, draft.not_applicable, problems
            claim_payload = [c.model_dump(mode="json") for c in claims]
            scenario_drafts, probe_set = await gather_all(
                self.call(
                    session,
                    "clarity:scenarios",
                    ScenarioDrafts,
                    prompts.SCENARIOS,
                    {**base, "claims": claim_payload},
                ),
                self.call(
                    session,
                    "clarity:decision-probes",
                    DecisionProbes,
                    prompts.DECISION_PROBES,
                    {
                        **base,
                        "claims": claim_payload,
                        "critic_questions": state.seeds,
                        "settled": [entry.question.question for entry in session.questions],
                    },
                ),
            )
            state.scenarios, scenario_problems = build_scenarios(scenario_drafts, claims)
            state.problems.extend(scenario_problems)
            probes = [p.model_copy(update={"id": f"P{i + 1}"}) for i, p in enumerate(probe_set.probes)]
            builders = []
            if probes:
                builder_payload = {
                    "north_star": base["north_star"],
                    "claims": claim_payload,
                    "probes": [p.model_dump(include={"id", "question", "options"}) for p in probes],
                }
                builders = await gather_all(
                    *[
                        self.call(
                            session,
                            f"clarity:candidate:{index + 1}",
                            Answers,
                            prompts.CANDIDATE,
                            builder_payload,
                        )
                        for index in range(CANDIDATES)
                    ]
                )
            asked = Counter(
                entry.question.id.split(":")[1]
                for entry in session.questions
                if entry.question.lens == "decision" and entry.question.id.startswith("D:")
            )
            decisions = settle(
                build_decisions(probes, [b.answers for b in builders], asked, state.thresholds),
                session.vetoes,
                session.questions,
            )
            attach_confirmations(decisions, state.scenarios)
            for decision in decisions:
                decision.quality = quality(decision, claims, state.scenarios)
            state.decisions = decisions
            state.review = await self.review(session, state, base)
            state.downstream_complete = True
        except (ModelError, ValueError) as error:
            state.failures.append(f"clarity: {error}"[:500])

    async def review(self, session, state, base):
        confirmed = [item.id for item in session.ledger if item.status == "confirmed"]
        mutated, canaries, id_map = plant(state.claims, confirmed, state.source_hash)
        by_id = {c.id: c for c in state.claims}
        checkable = [c for c in state.claims if c.status in ("confirmed", "derived")]
        review_call = self.call(
            session,
            "clarity:review",
            ClaimReview,
            prompts.REVIEW,
            {**base, "claims": [c.model_dump(mode="json") for c in mutated]},
        )
        roundtrip_call = self.call(
            session,
            "clarity:roundtrip",
            RoundTrip,
            prompts.ROUNDTRIP,
            {
                "claims": [c.text for c in state.claims if c.status != "proposal"],
                "scenarios": [s.model_dump(mode="json") for s in state.scenarios],
            },
        )
        if checkable:
            entail_call = self.call(
                session,
                "clarity:entailment",
                Entailment,
                prompts.ENTAILMENT,
                {
                    "claims": [
                        {
                            "claim_id": c.id,
                            "text": c.text,
                            "sources": [s.quote for s in c.spans],
                            "premises": [by_id[p].text for p in c.premises if p in by_id],
                        }
                        for c in checkable
                    ]
                },
            )
            review, roundtrip, entail = await gather_all(review_call, roundtrip_call, entail_call)
        else:
            review, roundtrip = await gather_all(review_call, roundtrip_call)
            entail = Entailment()
        result = score(review, canaries, id_map, state.thresholds)
        verdicts = {v.claim_id: v for v in entail.verdicts}
        result.entailment_failures = [
            c.id for c in checkable if c.id not in verdicts or not verdicts[c.id].entailed
        ]
        alignment = await self.call(
            session,
            "clarity:align",
            Alignment,
            prompts.ALIGN,
            {
                "restated": roundtrip.requirements,
                "ledger": [{"id": i.id, "text": i.text} for i in session.ledger if i.status == "confirmed"],
            },
        )
        result.roundtrip_missing = [key for key in alignment.missing_ledger_ids if key in set(confirmed)]
        return result

    def questions(self, session, state):
        from ..domain import Candidate

        question = follow_up(state.fields, state.suggestions or None, session.revision, state.assumed)
        if question:
            return [question]
        if not state.downstream_complete:
            return []
        open_decisions = [d for d in state.decisions if d.status == "open"]
        return [
            Candidate(
                id=d.id if d.id.startswith("V") else f"D:{d.category}:{session.revision}:{index + 1}",
                lens="decision",
                targets=[],
                question=d.question,
                options=d.options,
                code_diff=d.code_diff,
                divergence=3,
                uncertainty=3 if d.reversibility == "one-way" else 2,
                cost_to_change=3 if d.reversibility == "one-way" else 2,
            )
            for index, d in enumerate(open_decisions)
        ]
