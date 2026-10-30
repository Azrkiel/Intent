"""North Star checks: the application decides when a field is clear."""

import pytest

from backend.app.clarity.contracts import (
    FieldJudgement,
    FieldQuotes,
    FieldReading,
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
    OWN,
    accept_drafted,
    alpha_nominal,
    carry_passes,
    evaluate,
    fatigued,
    field_entries,
    field_texts,
    follow_up,
    next_target,
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


def asked(field, code, suggestion=False, options=("One", "Two"), probe=None):
    return Candidate(
        id=f"NS-{field}-{code}-r1",
        lens="north-star",
        question="Which one is it?",
        options=list(options),
        code_diff="Sets what the field says.",
        divergence=3,
        uncertainty=3,
        cost_to_change=3,
        suggestion=suggestion,
        probe=probe,
    )


def replay(*answers, quotes=None):
    """Answers as (question, text, picked) in order, as a session records them."""
    session = Session(north_star_quotes=quotes or {})
    for number, (question, text, picked) in enumerate(answers, 1):
        session.turns.append(Turn(number=number, text=text, question_id=question.id, suggested=picked))
        session.questions.append(AskedQuestion(question=question, answer=text, turn=number))
    return field_entries(session)


def test_a_picked_draft_replaces_the_field_and_needs_no_separate_read_back():
    draft = "Save an article to read later"
    question = asked("job", "J1", suggestion=True, options=(draft, "Track what I read"))
    entries = replay((question, draft, True), quotes={"job": "a tool"})
    assert entries["job"] == (draft, "drafted")
    session = Session()
    state = passing(text=draft)
    state.source = entries["job"].source
    accept_drafted([state], session)
    evaluate(state, set(), session.readbacks, Thresholds())
    assert state.passed


def test_typed_answers_extend_only_their_own_field():
    entries = replay(
        (asked("who-when", "W2"), "after breakfast", False),
        quotes={"who-when": "Just me", "job": "Save articles"},
    )
    assert entries["who-when"] == ("Just me … after breakfast", "user")
    assert entries["job"] == ("Save articles", "user")
    assert entries["good"] == ("", "user")


def test_a_typed_answer_keeps_the_picked_draft_and_then_needs_a_read_back():
    # Live probe 11: "Solo" dropped the picked draft and restored a fragment that failed W2.
    draft = "I open it on my phone after breakfast"
    pick = asked("who-when", "W2", suggestion=True, options=(draft, "Other draft here"))
    entries = replay((pick, draft, True), (asked("who-when", "W3"), "Solo", False))
    assert entries["who-when"] == (f"{draft} … Solo", "mixed")
    session = Session()
    state = passing(text=entries["who-when"].text)
    state.source = entries["who-when"].source
    accept_drafted([state], session)
    assert "job" not in session.readbacks


def test_an_edited_draft_replaces_the_field_and_an_unrelated_reply_does_not():
    draft = "I open it on my phone after breakfast"
    question = asked("who-when", "W2", suggestion=True, options=(draft, "Other draft here"))
    edited = "I open it on my laptop after breakfast"
    assert replay((question, edited, False), quotes={"who-when": "me"})["who-when"] == (edited, "mixed")
    assert replay((question, "Mostly weekends", False), quotes={"who-when": "me"})["who-when"] == (
        "me … Mostly weekends",
        "user",
    )


@pytest.mark.parametrize("reply", [KEEP, OWN, "idk", "not sure", "you decide"])
def test_replies_without_content_leave_the_field_alone(reply):
    assert replay((asked("job", "J1"), reply, False), quotes={"job": "Save"})["job"] == ("Save", "user")


def test_a_substantive_reply_starting_with_doubt_is_kept():
    reply = "Not sure, maybe once a week on my phone"
    assert replay((asked("job", "J1"), reply, False))["job"].text == reply


def test_a_reader_question_answer_keeps_its_question():
    probe = "Must it work on a phone?"
    entries = replay((asked("who-when", "G4", probe=probe), "Yes", False), quotes={"who-when": "Just me"})
    assert entries["who-when"].text == f"Just me … {probe} Yes"


def test_repeating_an_answer_does_not_grow_the_field():
    question = asked("job", "J1")
    entries = replay((question, "Save", False), (question, "Save", False))
    assert entries["job"] == ("Save", "user")


def test_follow_up_targets_the_field_next_target_names():
    reads, job = passing(), passing(field="job")
    reads.field, reads.passed, reads.failing = "who-when", False, ["G3"]
    job.passed, job.failing = False, ["J1"]
    target, codes = next_target([reads, job])
    assert target is job and codes == ["J1"]
    assert follow_up([reads, job], None, 1).id.startswith("NS-job-")
    reads.failing = ["G4:readers"]
    job.passed, job.failing = True, []
    assert next_target([reads, job]) is None and follow_up([reads, job], None, 1) is None


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


def reading(field, text, passed):
    verdicts = [RuleVerdict(rule=rule, passed=True, reason="ok") for rule in passed]
    return FieldReading(
        text=text,
        text_hash=text_hash(text),
        variation="perspective",
        judgement=FieldJudgement(field=field, readback="Read back.", verdicts=verdicts),
        probes=[],
        reader_a=[],
        reader_b=[],
    )


def judged(field, **rules):
    verdicts = [RuleVerdict(rule=rule, passed=ok, reason="why") for rule, ok in rules.items()]
    return FieldJudgement(field=field, readback="Read back.", verdicts=verdicts)


def test_added_words_cannot_fail_a_rule_the_text_already_passed():
    now = judged("who-when", W1=False, W2=False, W3=True, W4=False)
    before = reading("who-when", "Just me at breakfast", ["W1", "W2"])
    carry_passes(now, "Just me at breakfast … once a day", before)
    verdicts = {v.rule: v.passed for v in now.verdicts}
    assert verdicts == {"W1": False, "W2": True, "W3": True, "W4": False}  # W1 forbids wording


def test_a_rewrite_is_judged_on_its_own():
    now = judged("who-when", W2=False)
    carry_passes(now, "Something else entirely", reading("who-when", "Just me at breakfast", ["W2"]))
    assert not now.verdicts[0].passed
    carry_passes(now, "Anything", None)
    assert not now.verdicts[0].passed
