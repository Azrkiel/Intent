"""North Star field evaluation; the application decides when a field is clear."""

import hashlib
import re
from collections import Counter
from typing import TYPE_CHECKING

from .contracts import (
    FIELD_LABELS,
    NORTH_STAR_FIELDS,
    PROMPT_ONCE_RULES,
    RUBRIC,
    RULE_TEXT,
    FieldState,
    NorthStarDraft,
    Probe,
    ProbeAnswer,
    Thresholds,
)

if TYPE_CHECKING:
    from ..domain import Candidate, Session

KEEP = "Keep my wording"
OWN = "I'll describe it myself"
QUESTIONS = {
    "who-when": "Who will use this, and in what moment do they reach for it?",
    "job": "In one phrase, what job should this do for them?",
    "ambition": "How big is this meant to be?",
    "today": "How is this done today, and what goes wrong with that?",
    "good": "When it works, what result would you notice, ideally with a number?",
    "fails-if": "What would make you say it failed? Describe something you could see happen.",
}
EXAMPLES = {
    "who-when": ["Only me, on my laptop, several times a day", "Me and two friends, on our phones, weekly"],
    "job": ["Save something to come back to later", "Track whether I did something today"],
    "ambition": ["A personal tool only I use, for months", "Shared with a few people for a year"],
    "today": ["I keep browser tabs open and lose them", "I use a notes app that gets cluttered"],
    "good": ["Find what I saved in under 10 seconds", "Finish the task in under a minute"],
    "fails-if": ["If something I saved disappears after a reload", "If I can't tell what I already did"],
}
UNSURE = re.compile(
    r"^\s*(i\s*(do\s*n[o']?t|dunno)\s*know|idk|not sure|no idea|you decide|whatever|up to you)\b", re.I
)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slug(word: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", word.casefold()).strip("-")


def prompt_id(field: str, rule: str, word: str = "") -> str:
    return f"NS-{field}-{rule}" + (f"-{slug(word)}" if word else "")


def field_texts(draft: NorthStarDraft, user_texts: list[str]) -> tuple[dict[str, str], list[str]]:
    quotes: dict[str, list[str]] = {}
    problems = []
    for entry in draft.fields:
        for quote in entry.quotes:
            if any(quote in text for text in user_texts):
                quotes.setdefault(entry.field, []).append(quote)
            else:
                problems.append(f'North Star {entry.field} quote not found in your words: "{quote}"')
    return {field: " … ".join(dict.fromkeys(items)) for field, items in quotes.items()}, problems


def alpha_nominal(first: list[int], second: list[int]) -> float:
    """Krippendorff's alpha for two coders, nominal values, no missing data."""
    if len(first) != len(second) or not first:
        raise ValueError("Reader answers must align")
    counts = Counter([*first, *second])
    n = 2 * len(first)
    observed = 2 * sum(a != b for a, b in zip(first, second))
    expected = sum(counts[c] * counts[k] for c in counts for k in counts if c != k)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - (observed / n) / (expected / (n * (n - 1)))


def reader_result(probes: list[Probe], a: list[ProbeAnswer], b: list[ProbeAnswer]):
    if not probes:
        return None, [], [], False
    first, second = {x.probe_id: x.choice for x in a}, {x.probe_id: x.choice for x in b}
    ids = [probe.id for probe in probes]
    va, vb = [first.get(key, -1) for key in ids], [second.get(key, -1) for key in ids]
    disagree = [key for key, x, y in zip(ids, va, vb) if x != y]
    unclear = [key for key, x, y in zip(ids, va, vb) if -1 in (x, y)]
    one_way = any(probe.one_way and probe.id in disagree for probe in probes)
    return alpha_nominal(va, vb), disagree, unclear, one_way


def evaluate(
    state: FieldState, asked: set[str], readbacks: dict[str, str], thresholds: Thresholds
) -> FieldState:
    failing: list[str] = []
    if not state.text:
        failing.append("missing")
    else:
        judgement = state.judgement
        verdicts = {v.rule: v for v in (judgement.verdicts if judgement else [])}
        for rule in RUBRIC[state.field]:
            if rule not in verdicts:
                failing.append(f"judge:{rule}")
            elif not verdicts[rule].passed:
                failing.append(rule)
        rulings = {r.word.casefold(): r for r in (judgement.flag_rulings if judgement else [])}
        for flag in state.flags:
            ruling = rulings.get(flag.word)
            if (flag.auto or (ruling and ruling.prompt)) and prompt_id(
                state.field, "G1", flag.word
            ) not in asked:
                failing.append(f"G1:{flag.word}")
        for rule in PROMPT_ONCE_RULES.get(state.field, ()):
            verdict = verdicts.get(rule)
            if (verdict is None or not verdict.passed) and prompt_id(state.field, rule) not in asked:
                failing.append(rule)
        alpha, disagree, unclear, one_way = reader_result(state.probes, state.reader_a, state.reader_b)
        state.alpha = alpha
        if alpha is None:
            failing.append("G4:readers")
        else:
            failing.extend(f"G4:{key}" for key in unclear)
            if one_way or alpha < thresholds.alpha_pass:
                failing.extend(f"G4:{key}" for key in disagree)
        if readbacks.get(state.field) != state.text_hash:
            failing.append("G3")
    state.failing = list(dict.fromkeys(failing))
    state.passed = not state.failing
    return state


def _distinct(items) -> list[str]:
    seen, kept = set(), []
    for item in items:
        if item.strip() and item.casefold() not in seen:
            seen.add(item.casefold())
            kept.append(item)
    return kept


def _options(*groups: list[str]) -> list[str]:
    options = _distinct(item for group in groups for item in group)[:3]
    for filler in (OWN, KEEP):
        if len(options) >= 2:
            break
        if filler not in options:
            options.append(filler)
    return options


def _question(state: FieldState, code: str, revision: int) -> tuple[str, list[str], str]:
    label = FIELD_LABELS[state.field]
    verdicts = {v.rule: v for v in (state.judgement.verdicts if state.judgement else [])}
    if code == "missing" or code.startswith("judge:"):
        return (
            QUESTIONS[state.field],
            _options(EXAMPLES[state.field]),
            f"{prompt_id(state.field, 'missing')}-r{revision}",
        )
    if code.startswith("G1:"):
        word = code[3:]
        ruling = next(
            (
                r
                for r in (state.judgement.flag_rulings if state.judgement else [])
                if r.word.casefold() == word
            ),
            None,
        )
        options = _options((ruling.options if ruling else [])[:2], [KEEP])
        return (
            f'You said "{word}" in {label}. What exactly do you mean?',
            options,
            prompt_id(state.field, "G1", word),
        )
    if code.startswith("G4:"):
        probe = next((p for p in state.probes if p.id == code[3:]), None)
        if probe:
            return (
                f"In {label}: {probe.question}",
                _options(probe.options),
                f"{prompt_id(state.field, 'G4')}-r{revision}",
            )
        return (
            QUESTIONS[state.field],
            _options(EXAMPLES[state.field]),
            f"{prompt_id(state.field, 'G4')}-r{revision}",
        )
    verdict = verdicts.get(code)
    reason = f" {verdict.reason}" if verdict else ""
    if code in PROMPT_ONCE_RULES.get(state.field, ()):
        options = _options((verdict.options if verdict else [])[:2], [KEEP])
        return f"For {label}, can you {RULE_TEXT[code]}?{reason}", options, prompt_id(state.field, code)
    options = _options(verdict.options if verdict else [], EXAMPLES[state.field])
    return (
        f"For {label}, please {RULE_TEXT[code]}.{reason}",
        options,
        f"{prompt_id(state.field, code)}-r{revision}",
    )


def follow_up(
    fields: list[FieldState], drafts: list[str] | None, revision: int, assumed: list[str] = ()
) -> "Candidate | None":
    """Propose and confirm: a vague answer gets Intent's extrapolated draft to check."""
    from ..domain import Candidate

    by_field = {state.field: state for state in fields}
    for name in NORTH_STAR_FIELDS:
        state = by_field.get(name)
        if state is None or state.passed:
            continue
        codes = [code for code in state.failing if code not in ("G3", "G4:readers")]  # readers: see failures
        if not codes:
            continue  # only the read-back confirmation remains; the UI asks for it
        question, options, key = _question(state, codes[0], revision)
        if drafts:
            guess = f' My best guess from what you told me: "{drafts[0]}".'
            filled = f" I filled in: {'; '.join(assumed)}." if assumed else ""
            question = f"{question}{guess}{filled} Does that fit? Pick one, or edit it."
            keep = [KEEP] if KEEP in options else []
            options = _distinct([*drafts[: 3 - len(keep)], *keep])
        return Candidate(
            id=key,
            lens="north-star",
            targets=[],
            question=question[:500],
            options=options,
            code_diff=f"The {FIELD_LABELS[name]} answer sets which builds are proportionate "
            "and which choices Intent may make for you.",
            divergence=3,
            uncertainty=3,
            cost_to_change=3,
            suggestion=bool(drafts),
        )
    return None


def accept_drafted(fields: list[FieldState], session: "Session") -> None:
    """A field quoted only from drafts the user picked needs no separate read-back.

    A quote that also occurs in a typed turn may be the user's own words, so it still needs one.
    """
    drafted = [turn.text for turn in session.turns if turn.suggested]
    typed = [turn.text for turn in session.turns if not turn.suggested]
    for state in fields:
        parts = state.text.split(" … ") if state.text else []
        if parts and all(
            any(part in text for text in drafted) and not any(part in text for text in typed)
            for part in parts
        ):
            session.readbacks[state.field] = state.text_hash


def fatigued(session: "Session") -> bool:
    clicked = {asked.turn for asked in session.questions if asked.answer in asked.question.options}
    typed = [turn.text.strip() for turn in session.turns if turn.number not in clicked and not turn.suggested]
    if len(typed) >= 2 and all(UNSURE.search(text) for text in typed[-2:]):
        return True
    if len(typed) >= 2 and all(len(text.split()) == 1 for text in typed[-2:]):
        return True
    if len(typed) >= 5:
        baseline = sum(len(text) for text in typed[:3]) / 3
        return sum(len(text) for text in typed[-2:]) / 2 <= baseline / 2
    return False
