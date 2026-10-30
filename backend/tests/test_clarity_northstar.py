"""North Star checks: the application decides when a field is clear."""

import pytest

from backend.app.clarity.contracts import (
    FieldJudgement,
    FieldQuotes,
    FieldState,
    FlagRuling,
    NorthStarDraft,
    Probe,
    ProbeAnswer,
    RuleVerdict,
    Thresholds,
)
from backend.app.clarity.lexicon import scan
from backend.app.clarity.northstar import (
    KEEP,
    accept_drafted,
    alpha_nominal,
    evaluate,
    fatigued,
    field_texts,
    follow_up,
    prompt_id,
    text_hash,
)
from backend.app.domain import AskedQuestion, Candidate, Session, Turn


def test_lexicon_prompts_reliable_smells_and_routes_weak_ones_to_a_judge():
    flags = {f.word: f for f in scan("Make it fast and easy, etc., if necessary, 100% of the time")}
    assert flags["fast"].auto and flags["easy"].auto and flags["etc"].auto and flags["if necessary"].auto
    assert not flags["it"].auto and not flags["100%"].auto
    assert "no" not in {f.word for f in scan("Reject non-https URLs")}


def test_alpha_matches_a_hand_computed_case_and_perfect_agreement():
    assert alpha_nominal([0, 0, 1, 1], [0, 0, 1, 0]) == pytest.approx(16 / 30)
    assert alpha_nominal([0, 1, 0, 1], [0, 1, 0, 1]) == 1.0
    assert alpha_nominal([0, 0, 0], [0, 0, 0]) == 1.0


def test_field_quotes_must_be_the_users_words():
    texts, problems = field_texts(
        NorthStarDraft(fields=[FieldQuotes(field="job", quotes=["save an article", "invented"])]),
        ["I want to save an article to read later"],
    )
    assert texts == {"job": "save an article"}
    assert problems and "invented" in problems[0]


def passing(field="job", text="save an article to read later", **extra):
    probes = [Probe(id=f"{field}.p{i}", question=f"Q{i}?", options=["Yes", "No"]) for i in range(6)]
    state = FieldState(
        field=field,
        text=text,
        text_hash=text_hash(text),
        flags=scan(text),
        probes=probes,
        judgement=FieldJudgement(
            field=field,
            readback="You want to save an article for later.",
            verdicts=[
                RuleVerdict(rule=rule, passed=True, reason="ok") for rule in ("J1", "J2", "O1", "O2", "O3")
            ],
        ),
        reader_a=[ProbeAnswer(probe_id=p.id, choice=0) for p in probes],
        reader_b=[ProbeAnswer(probe_id=p.id, choice=0) for p in probes],
    )
    return state.model_copy(update=extra)


def test_field_passes_only_after_rubric_readers_and_read_back():
    state = passing()
    evaluate(state, set(), {}, Thresholds())
    assert state.failing == ["G3"]
    evaluate(state, set(), {"job": state.text_hash}, Thresholds())
    assert state.passed


def test_vague_word_is_prompted_once_then_kept_wording_passes():
    state = passing(text="save an article fast")
    state.flags = scan(state.text)
    readbacks = {"job": state.text_hash}
    evaluate(state, set(), readbacks, Thresholds())
    assert state.failing == ["G1:fast"]
    evaluate(state, {prompt_id("job", "G1", "fast")}, readbacks, Thresholds())
    assert state.passed


def test_weak_flag_prompts_only_when_the_judge_says_so():
    state = passing(text="save it for later")
    state.flags = scan(state.text)
    state.judgement.flag_rulings = [FlagRuling(word="it", prompt=False, reason="clear referent")]
    evaluate(state, set(), {"job": state.text_hash}, Thresholds())
    assert state.passed


def test_measurable_outcome_is_prompt_once_not_blocking():
    state = passing(field="good", text="find a saved article quickly")
    state.flags = []
    state.judgement.verdicts[3] = RuleVerdict(
        rule="O2", passed=False, reason="no number", options=["Under 10 seconds"]
    )
    evaluate(state, set(), {"good": state.text_hash}, Thresholds())
    assert state.failing == ["O2"]
    evaluate(state, {prompt_id("good", "O2")}, {"good": state.text_hash}, Thresholds())
    assert state.passed


@pytest.mark.parametrize("b_choice, expected", [(1, "G4:job.p0"), (-1, "G4:job.p0")])
def test_reader_disagreement_or_cannot_tell_fails(b_choice, expected):
    state = passing()
    state.reader_b[0] = ProbeAnswer(probe_id="job.p0", choice=b_choice)
    evaluate(state, set(), {"job": state.text_hash}, Thresholds())
    assert expected in state.failing


def test_missing_rule_verdict_is_a_judge_failure_not_a_pass():
    state = passing()
    state.judgement.verdicts = state.judgement.verdicts[1:]
    evaluate(state, set(), {"job": state.text_hash}, Thresholds())
    assert "judge:J1" in state.failing


def test_follow_up_targets_one_rule_with_options_and_respects_field_order():
    who = FieldState(field="who-when", text="", text_hash=text_hash(""))
    job = passing(text="save an article fast")
    job.flags = scan(job.text)
    for state in (who, job):
        evaluate(state, set(), {}, Thresholds())
    question = follow_up([job, who], None, 3)
    assert question.lens == "north-star" and question.id.startswith("NS-who-when-missing")
    job_question = follow_up([job], None, 3)
    assert job_question.id == prompt_id("job", "G1", "fast")
    assert KEEP in job_question.options and 2 <= len(job_question.options) <= 3


def test_vague_answers_get_an_extrapolated_draft_to_confirm():
    job = passing(text="")
    evaluate(job, set(), {}, Thresholds())
    drafts = ["Save an article to read later", "Collect links to read on weekends"]
    question = follow_up([job], drafts, 2, ["you read on a laptop"])
    assert question.suggestion and question.options[:2] == drafts
    assert "My best guess" in question.question and "you read on a laptop" in question.question
    vague = passing(text="save an article fast")
    vague.flags = scan(vague.text)
    evaluate(vague, set(), {}, Thresholds())
    assert KEEP in follow_up([vague], drafts, 2).options


def test_a_field_built_from_picked_drafts_needs_no_separate_read_back():
    turns = [
        Turn(number=1, text="a tool"),
        Turn(number=2, text="Save an article to read later", suggested=True),
    ]
    session = Session(turns=turns)
    state = passing(text="Save an article to read later")
    accept_drafted([state], session)
    evaluate(state, set(), session.readbacks, Thresholds())
    assert state.passed
    other = Session(turns=turns)
    accept_drafted([passing(text="a tool … Save an article to read later")], other)
    assert "job" not in other.readbacks


def test_fatigue_signals_ignore_clicked_options():
    session = Session(
        turns=[
            Turn(number=i + 1, text=t)
            for i, t in enumerate(
                [
                    "I want a reading queue on my laptop for articles I find during work",
                    "Only me, every weekday when I find something long",
                    "Today I leave tabs open and lose them when Chrome restarts",
                    "idk",
                    "you decide",
                ]
            )
        ]
    )
    assert fatigued(session)
    option = Candidate(
        lens="north-star",
        question="Which?",
        options=["Under 10 seconds", "Under a minute"],
        code_diff="Sets the measurable outcome.",
        divergence=3,
        uncertainty=3,
        cost_to_change=3,
    )
    session.turns = session.turns[:3] + [Turn(number=4, text="Under 10 seconds")]
    session.questions = [AskedQuestion(question=option, answer="Under 10 seconds", turn=4)]
    assert not fatigued(session)
