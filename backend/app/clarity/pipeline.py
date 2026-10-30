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
    REWRITE_RULES,
    RUBRIC,
    RULE_TEXT,
    Alignment,
    Answers,
    ClaimMapDraft,
    ClaimReview,
    ClarityState,
    DecisionProbes,
    Entailment,
    FieldReading,
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
from .northstar import (
    QUESTIONS,
    accept_drafted,
    carry_passes,
    evaluate,
    fatigued,
    field_entries,
    field_texts,
    follow_up,
    next_target,
    question_field,
    settled_probes,
    text_hash,
)
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
        await self.extract_fields(session)
        entries = field_entries(session)
        state.fields = [
            FieldState(
                field=name,
                text=entries[name].text,
                source=entries[name].source,
                text_hash=text_hash(entries[name].text),
                flags=scan(entries[name].text),
            )
            for name in NORTH_STAR_FIELDS
        ]
        fresh = []
        for f in state.fields:
            reading = session.north_star_readings.get(f.field)
            if (
                f.text
                and reading
                and reading.text_hash == f.text_hash
                and reading.variation == session.clarity_reader_variation
            ):
                f.judgement, f.probes = reading.judgement, reading.probes
                f.reader_a, f.reader_b = reading.reader_a, reading.reader_b
            elif f.text:
                fresh.append(f)
        if fresh:
            await self.read_fields(session, state, fresh)
        accept_drafted(state.fields, session)
        self.refresh_fields(session, state)
        state.fatigued = fatigued(session)  # recorded for evals; drafting does not wait for fatigue
        chosen = next_target(state.fields)
        if chosen:
            await self.draft_answers(session, state, *chosen)

    async def extract_fields(self, session):
        """Quote the user's free-form turns into empty fields; answers belong to the field they answer."""
        turns = [
            t
            for t in session.turns
            if t.number > session.north_star_read_through and question_field(t.question_id) is None
        ]
        entries = field_entries(session)
        if turns and not all(entry.text for entry in entries.values()):
            draft = await self.call(
                session,
                "clarity:north-star",
                NorthStarDraft,
                prompts.NORTH_STAR,
                {"turns": [{"number": t.number, "text": t.text} for t in turns]},
            )
            # Invalid quotes are dropped, like ledger sources.
            texts, _ = field_texts(draft, [t.text for t in turns])
            for name, text in texts.items():
                if not entries[name].text:
                    session.north_star_quotes[name] = text
        session.north_star_read_through = len(session.turns)

    async def read_fields(self, session, state, present):
        """Judge and read fields whose text changed, and keep complete results for that text."""
        previous = {
            f.field: session.north_star_readings[f.field]
            for f in present
            if f.field in session.north_star_readings
        }
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
                    **(
                        {
                            "previous": {
                                "text": previous[f.field].text,
                                "passed": [
                                    v.rule for v in previous[f.field].judgement.verdicts if v.passed
                                ],
                            }
                        }
                        if f.field in previous
                        else {}
                    ),
                }
                for f in present
            ]
        }
        # A field keeps its questions and settled answers: regenerating them on every edit gave each
        # answer a fresh chance to fail, and rubric and readers never passed together (live probe 14).
        kept = {
            name: reading
            for name, reading in previous.items()
            if reading.variation == session.clarity_reader_variation
        }
        unprobed = [f for f in present if f.field not in kept]
        rubric_call = self.call(
            session, "clarity:rubric", RubricJudgement, prompts.RUBRIC_JUDGE, judge_payload
        )
        if unprobed:
            judgement, probe_sets = await gather_all(
                rubric_call,
                self.call(
                    session,
                    "clarity:probes",
                    NorthStarProbes,
                    prompts.READER_PROBES,
                    {
                        "fields": [
                            {"field": f.field, "scope": QUESTIONS[f.field], "text": f.text}
                            for f in unprobed
                        ]
                    },
                ),
            )
            sets = {entry.field: entry.probes for entry in probe_sets.sets}
        else:
            judgement, sets = await rubric_call, {}
        judged = {entry.field: entry for entry in judgement.fields}
        settled = {}
        for f in present:
            f.judgement = judged.get(f.field)
            if f.judgement:
                carry_passes(f.judgement, f.text, previous.get(f.field))
            if f.field in kept:
                f.probes = kept[f.field].probes
                settled[f.field] = settled_probes(kept[f.field])
            else:
                f.probes = [
                    p.model_copy(update={"id": f"{f.field}.p{i + 1}"})
                    for i, p in enumerate(sets.get(f.field, []))
                ]
                settled[f.field] = set()
        state.failures.extend(
            f"clarity: reader probes missing for {FIELD_LABELS[f.field]}" for f in present if not f.probes
        )
        reader_payload = {
            "fields": [
                {
                    "field": f.field,
                    "text": f.text,
                    "questions": [
                        p.model_dump(include={"id", "question", "options"})
                        for p in f.probes
                        if p.id not in settled[f.field]
                    ],
                }
                for f in present
                if any(p.id not in settled[f.field] for p in f.probes)
            ]
        }
        first, second = Answers(answers=[]), Answers(answers=[])
        if reader_payload["fields"]:
            role_b, prompt_b = READER_B[session.clarity_reader_variation]
            first, second = await gather_all(
                self.call(session, "clarity:reader:a", Answers, prompts.READER, reader_payload),
                self.call(session, role_b, Answers, prompt_b, reader_payload),
            )
        for f in present:
            ids = {p.id for p in f.probes}
            reading = kept.get(f.field)
            kept_a = [x for x in reading.reader_a if x.probe_id in settled[f.field]] if reading else []
            kept_b = [x for x in reading.reader_b if x.probe_id in settled[f.field]] if reading else []
            f.reader_a = kept_a + [
                x for x in first.answers if x.probe_id in ids - settled[f.field]
            ]
            f.reader_b = kept_b + [
                x for x in second.answers if x.probe_id in ids - settled[f.field]
            ]
            complete = (
                f.judgement
                and f.probes
                and ids <= {x.probe_id for x in f.reader_a}
                and ids <= {x.probe_id for x in f.reader_b}
                and set(RUBRIC[f.field]) <= {v.rule for v in f.judgement.verdicts}
            )
            if complete:
                session.north_star_readings[f.field] = FieldReading(
                    text=f.text,
                    text_hash=f.text_hash,
                    variation=session.clarity_reader_variation,
                    judgement=f.judgement,
                    probes=f.probes,
                    reader_a=f.reader_a,
                    reader_b=f.reader_b,
                )

    async def draft_answers(self, session, state, target, failing):
        probes = {f"G4:{p.id}": p.question for p in target.probes}
        verdicts = target.judgement.verdicts if target.judgement else []
        passing = [RULE_TEXT[v.rule] for v in verdicts if v.passed and v.rule in RUBRIC[target.field]]
        # A rewrite re-rolled the rules the text passed (live probes 9, 12), so extend the text unless
        # it needs words removed or has nothing worth keeping. Options hold 250 characters.
        removal = REWRITE_RULES | {f"G1:{flag.word}" for flag in target.flags if flag.auto}
        extendable = not removal & set(failing) and (passing or all(c in probes for c in failing))
        keep = target.text if extendable and 0 < len(target.text) <= 180 else None
        drafts = await self.call(
            session,
            "clarity:suggest",
            Suggestions,
            prompts.SUGGEST,
            {
                "field": target.field,
                "label": FIELD_LABELS[target.field],
                "scope": QUESTIONS[target.field],
                "current": target.text,
                "failing": [
                    f'settle a question a reader could not answer: "{probes[code]}"'
                    if code in probes
                    else describe(code)
                    for code in failing
                ],
                "turns": [t.text for t in session.turns],
                **({"keep": keep} if keep else {"still_satisfy": passing}),
            },
        )
        screened = [
            d
            for d in drafts.drafts
            if not any(flag.auto for flag in scan(d[len(keep) :] if keep else d))
            and (not keep or d.startswith(keep))
        ]
        state.dropped_suggestions = [d for d in drafts.drafts if d not in screened]
        state.suggestions = screened if len(screened) >= 2 else []
        state.suggestions_field = target.field if state.suggestions else None
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
        # A planted defect can hide the only claim citing a ledger item, so an accurate reviewer
        # reports that item as omitted. That is the plant's doing, not a gap in the real claims.
        planted = {id_map[c.target] for c in canaries if c.target in id_map}
        hidden = {s.item_id for c in state.claims if c.id in planted for s in c.spans}
        result.omitted_ledger_ids = [key for key in result.omitted_ledger_ids if key not in hidden]
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

        target = next_target(state.fields)
        drafts = state.suggestions if target and target[0].field == state.suggestions_field else None
        question = follow_up(state.fields, drafts, session.revision, state.assumed)
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
