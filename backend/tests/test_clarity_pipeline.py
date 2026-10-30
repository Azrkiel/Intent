"""Clarity v2 orchestration with scripted models; not evidence of live model quality."""

import asyncio

import pytest

from backend.app.clarity.contracts import Answers, ClaimReview, ProbeAnswer
from backend.app.demo import DemoModels
from backend.app.domain import gate_for
from backend.app.engine import Engine
from backend.app.models import ModelError
from backend.app.store import Store
from backend.tests.clarity_fixtures import reading_queue_session


async def confirm_all(engine, session):
    for field in list(session.clarity.fields):
        if field.failing == ["G3"]:
            await engine.confirm_readback(session, field.field, field.text_hash)


async def analyzed(tmp_path, models=None, answered=True):
    engine = Engine(Store(str(tmp_path / "db")), models or DemoModels())
    session = reading_queue_session(answered)
    [event async for event in engine.analyze(session)]
    return engine, session


async def test_scripted_v2_session_needs_read_backs_then_passes(tmp_path):
    engine, session = await analyzed(tmp_path)
    assert not gate_for(session).ready
    assert all(f.failing == ["G3"] for f in session.clarity.fields)
    await confirm_all(engine, session)
    assert session.clarity.downstream_complete and session.clarity.review.trusted
    assert session.clarity.scenarios
    assert gate_for(session).ready, gate_for(session).blockers


async def test_reader_disagreement_asks_a_north_star_question(tmp_path):
    class Disagree(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            result = await super().call(session, role, schema, instruction, payload)
            if role == "clarity:reader:b":
                first = result.answers[0]
                result.answers[0] = ProbeAnswer(probe_id=first.probe_id, choice=1)
            return result

    _, session = await analyzed(tmp_path, Disagree())
    assert session.current_question.lens == "north-star"
    assert "G4" in session.current_question.id
    assert not gate_for(session).ready


async def test_reader_disagreement_drafts_extend_the_field_instead_of_rewriting_it(tmp_path):
    # Live probe 9: the field passed every rubric rule, then a G4 draft rewrote it, dropped
    # "at 7 am" and W2 failed again.
    from backend.app.clarity.contracts import Suggestions

    class Disagree(DemoModels):
        payload = None

        async def call(self, session, role, schema, instruction, payload):
            result = await super().call(session, role, schema, instruction, payload)
            if role == "clarity:reader:b":
                first = result.answers[0]
                result.answers[0] = ProbeAnswer(probe_id=first.probe_id, choice=1)
            if role == "clarity:suggest":
                self.payload = payload
                keep = payload["keep"]
                return Suggestions(drafts=[f"{keep}, on my phone", f"{keep}, on my laptop", "A rewrite"])
            return result

    models = Disagree()
    _, session = await analyzed(tmp_path, models)
    field = next(f for f in session.clarity.fields if f.field == models.payload["field"])
    probe = next(p for p in field.probes if f"G4:{p.id}" in field.failing)
    assert models.payload["keep"] == field.text
    assert any(probe.question in item for item in models.payload["failing"])
    question = session.current_question
    assert "G4" in question.id and "A rewrite" not in question.options
    assert all(option.startswith(field.text) for option in question.options if option != "Keep my wording")


@pytest.mark.parametrize("role", ["clarity:north-star", "clarity:claims", "clarity:review"])
async def test_failed_passes_keep_the_gate_closed(tmp_path, role):
    class Fails(DemoModels):
        async def call(self, session, r, schema, instruction, payload):
            if r == role:
                raise ModelError(f"{role} timed out")
            return await super().call(session, r, schema, instruction, payload)

    engine, session = await analyzed(tmp_path, Fails())
    if session.clarity.fields and all(f.failing == ["G3"] for f in session.clarity.fields):
        await confirm_all(engine, session)
    assert not gate_for(session).ready


async def test_reviewer_that_misses_canaries_is_untrusted(tmp_path):
    class Blind(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "clarity:review":
                return ClaimReview()
            return await super().call(session, role, schema, instruction, payload)

    engine, session = await analyzed(tmp_path, Blind())
    await confirm_all(engine, session)
    assert not session.clarity.review.trusted
    assert any("could not be verified" in b for b in gate_for(session).blockers)


async def test_divergent_candidates_create_an_open_decision(tmp_path):
    from backend.app.clarity.contracts import DecisionProbe, DecisionProbes

    class Diverge(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "clarity:decision-probes":
                return DecisionProbes(
                    probes=[
                        DecisionProbe(
                            id="x",
                            question="Where do saved links live?",
                            options=["localStorage", "IndexedDB"],
                            code_diff="Synchronous key/value storage versus an async object store",
                            context="Persistence (C4)",
                            drivers=["fails-if"],
                            kano="must-be",
                            category="data-model",
                            claims=["C4"],
                        )
                    ]
                )
            if role.startswith("clarity:candidate:"):
                index = int(role.rsplit(":", 1)[1])
                return Answers(answers=[ProbeAnswer(probe_id=payload["probes"][0]["id"], choice=index % 2)])
            return await super().call(session, role, schema, instruction, payload)

    engine, session = await analyzed(tmp_path, Diverge())
    await confirm_all(engine, session)
    [decision] = session.clarity.decisions
    assert (decision.reversibility, decision.status) == ("one-way", "open")
    assert session.current_question.lens == "decision"
    assert not gate_for(session).ready


async def test_unanswered_field_gets_a_draft_and_picking_it_settles_the_field(tmp_path):
    engine, session = await analyzed(tmp_path, answered=False)
    question = session.current_question
    assert question.id.startswith("NS-who-when") and question.suggestion
    assert "My best guess" in question.question and "I filled in" in question.question
    [event async for event in engine.turn(session, question.options[0])]
    assert session.turns[-1].suggested
    who = next(f for f in session.clarity.fields if f.field == "who-when")
    assert who.passed  # picked draft: rubric passes and no separate read-back is needed


async def test_a_picked_draft_replaces_the_field_whole_and_is_not_flag_checked(tmp_path):
    # Live extraction quoted a fragment of the picked draft, dropping the device and frequency it
    # added, so W3/W4 kept failing; its "every" then drew a vague-word question about Intent's words.
    from backend.app.clarity.contracts import FieldQuotes, NorthStarDraft

    class Fragments(DemoModels):
        seen = []

        async def call(self, session, role, schema, instruction, payload):
            result = await super().call(session, role, schema, instruction, payload)
            if role == "clarity:north-star":
                picked = [t.text for t in session.turns if t.suggested]
                if picked:
                    fields = [f for f in result.fields if f.field != "who-when"]
                    fragment = FieldQuotes(field="who-when", quotes=[picked[-1][:12]])
                    result = NorthStarDraft(fields=[*fields, fragment])
            if role == "clarity:rubric":
                self.seen = [f for f in payload["fields"] if f["field"] == "who-when"]
            return result

    models = Fragments()
    engine, session = await analyzed(tmp_path, models, answered=False)
    question = session.current_question
    draft = "Every weekday I open it on my phone after breakfast"
    question.options = [draft, *question.options[1:]]
    [event async for event in engine.turn(session, draft)]
    who = next(f for f in session.clarity.fields if f.field == "who-when")
    assert who.text == draft and who.flags == []
    assert models.seen and models.seen[0]["text"] == draft and models.seen[0]["flags"] == []


async def test_drafts_are_written_for_the_field_the_follow_up_asks_about(tmp_path):
    # A field missing reader probes is skipped by follow_up, so drafting it put its drafts on the
    # next field's question.
    from backend.app.clarity.contracts import NorthStarProbes, RubricJudgement

    class SkippedField(DemoModels):
        drafted = []

        async def call(self, session, role, schema, instruction, payload):
            result = await super().call(session, role, schema, instruction, payload)
            if role == "clarity:probes":
                return NorthStarProbes(sets=[s for s in result.sets if s.field != "who-when"])
            if role == "clarity:rubric":
                for field in result.fields:
                    if field.field == "job":
                        field.verdicts[0].passed = False
                return RubricJudgement(fields=result.fields)
            if role == "clarity:suggest":
                self.drafted.append(payload["field"])
            return result

    models = SkippedField()
    _, session = await analyzed(tmp_path, models, answered=True)
    assert models.drafted and set(models.drafted) == {"job"}
    assert session.current_question.id.startswith("NS-job-") and session.current_question.suggestion


async def test_probes_and_drafts_are_scoped_to_their_field(tmp_path):
    # Live probes asked builder questions under Who & when ("one entry per habit?") that the field
    # can never settle, and drafts restated sync and login; both kept the field failing.
    from backend.app.clarity import prompts
    from backend.app.clarity.northstar import QUESTIONS

    class Payloads(DemoModels):
        seen = {}

        async def call(self, session, role, schema, instruction, payload):
            self.seen[role] = payload
            return await super().call(session, role, schema, instruction, payload)

    models = Payloads()
    await analyzed(tmp_path, models, answered=False)
    probes = models.seen["clarity:probes"]["fields"]
    assert probes and all(entry["scope"] == QUESTIONS[entry["field"]] for entry in probes)
    suggest = models.seen["clarity:suggest"]
    assert suggest["scope"] == QUESTIONS[suggest["field"]]
    assert "scope" in prompts.READER_PROBES and "scope" in prompts.SUGGEST


async def test_the_judge_sees_the_rules_a_field_passed_last_time(tmp_path):
    # Live, the judge re-judged from scratch each round: W2 passed at round 4 and failed at round 7.
    from backend.app.clarity import prompts
    from backend.app.domain import Session

    class Judged(DemoModels):
        payloads = []

        async def call(self, session, role, schema, instruction, payload):
            if role == "clarity:rubric":
                self.payloads.append(payload)
            return await super().call(session, role, schema, instruction, payload)

    models = Judged()
    engine, session = await analyzed(tmp_path, models, answered=True)
    who = next(f for f in session.clarity.fields if f.field == "who-when")
    prior = session.rubric_passes["who-when"]
    assert prior.text == who.text and set(prior.passed) == {"W1", "W2", "W3", "W4"}
    assert all("previous" not in entry for entry in models.payloads[0]["fields"])
    [event async for event in engine.turn(session, "I also check it on my laptop at lunch.")]
    entry = next(e for e in models.payloads[-1]["fields"] if e["field"] == "who-when")
    assert entry["previous"] == {"text": prior.text, "passed": prior.passed}
    assert "previous" in prompts.RUBRIC_JUDGE
    restored = Session.model_validate_json(session.model_dump_json(round_trip=True))
    assert restored.rubric_passes == session.rubric_passes


async def test_demo_fields_show_distinct_text_from_the_conversation(tmp_path):
    engine, session = await analyzed(tmp_path)
    texts = [f.text for f in session.clarity.fields]
    assert all(texts) and len(set(texts)) == 6
    assert next(f.text for f in session.clarity.fields if f.field == "today").startswith("I keep links")


async def test_demo_v2_asks_north_star_and_decision_questions_not_slot_questions(tmp_path):
    engine, session = await analyzed(tmp_path, answered=False)
    asked = []
    for _ in range(12):
        question = session.current_question
        if question is None:
            await confirm_all(engine, session)
            question = session.current_question
        if question is None:
            break
        asked.append(question.lens)
        [event async for event in engine.turn(session, question.options[0])]
        await confirm_all(engine, session)
    assert set(asked) == {"north-star", "decision"}
    assert gate_for(session).ready, gate_for(session).blockers


async def test_new_utterance_clears_clarity_but_keeps_read_backs(tmp_path):
    engine, session = await analyzed(tmp_path)
    await confirm_all(engine, session)
    saved = dict(session.readbacks)
    stream = engine.turn(session, "Also let me tag articles")
    first = await anext(stream)
    assert first["session"]["clarity"] is None and session.readbacks == saved
    await stream.aclose()


async def test_v1_sessions_still_use_the_framework_map(tmp_path):
    calls = []

    class Track(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            calls.append(role)
            return await super().call(session, role, schema, instruction, payload)

    session = reading_queue_session()
    session.clarity_version = 1
    [event async for event in Engine(Store(str(tmp_path / "db")), Track()).analyze(session)]
    assert "framework:map" in calls and not any(r.startswith("clarity:") for r in calls)


async def test_a_failed_parallel_call_cancels_its_siblings(tmp_path):
    finished = []

    class Fails(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "clarity:reader:a":
                raise ModelError("reader a timed out")
            if role == "clarity:reader:b":
                await asyncio.sleep(0.2)
                finished.append(role)
            return await super().call(session, role, schema, instruction, payload)

    _, session = await analyzed(tmp_path, Fails())
    await asyncio.sleep(0.4)
    assert session.clarity.failures and not finished


async def test_a_field_without_reader_probes_is_a_failure_not_a_repeating_question(tmp_path):
    from backend.app.clarity.contracts import NorthStarProbes

    class NoProbes(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            if role == "clarity:probes":
                return NorthStarProbes(sets=[])
            return await super().call(session, role, schema, instruction, payload)

    engine, session = await analyzed(tmp_path, NoProbes())
    assert any("reader probes missing for" in f for f in session.clarity.failures)
    blockers = gate_for(session).blockers
    assert any("reader probes missing for" in b for b in blockers)
    assert not gate_for(session).ready
    question = session.current_question
    assert question is None or "G4" not in question.id
    assert not gate_for(session).ready
