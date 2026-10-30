"""Clarity v2 orchestration with scripted models; not evidence of live model quality."""

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


async def analyzed(tmp_path, models=None):
    engine = Engine(Store(str(tmp_path / "db")), models or DemoModels())
    session = reading_queue_session()
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


async def test_vague_field_gets_a_draft_and_picking_it_settles_the_field(tmp_path):
    from backend.app.clarity.contracts import RuleVerdict

    class Vague(DemoModels):
        async def call(self, session, role, schema, instruction, payload):
            result = await super().call(session, role, schema, instruction, payload)
            if role == "clarity:rubric":
                for field in result.fields:
                    entry = next(e for e in payload["fields"] if e["field"] == field.field)
                    if field.field == "who-when" and not entry["text"].startswith("Scripted draft"):
                        field.verdicts[1] = RuleVerdict(rule="W2", passed=False, reason="No moment named")
            return result

    engine, session = await analyzed(tmp_path, Vague())
    question = session.current_question
    assert question.suggestion and "My best guess" in question.question and "I filled in" in question.question
    [event async for event in engine.turn(session, question.options[0])]
    assert session.turns[-1].suggested
    who = next(f for f in session.clarity.fields if f.field == "who-when")
    assert who.passed  # picked draft: rubric passes and no separate read-back is needed


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
