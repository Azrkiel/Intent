"""Versioned vague-word lists (INCOSE GtWR R7-R9, R26; Femmer et al. 2017 smells)."""

import re

from .contracts import LexiconFlag

LEXICON_VERSION = "2026-10-29.1"
# Measured precision (Femmer et al.): subjective 0.96, vague adverbs/adjectives 0.81,
# loopholes 0.72, open-ended 0.70 -> prompt automatically. Others need a judge first.
AUTO = frozenset({"subjective", "vague", "escape", "open-ended"})
LEXICON: dict[str, tuple[str, ...]] = {
    "subjective": (
        "easy",
        "easily",
        "simple",
        "simply",
        "nice",
        "intuitive",
        "user-friendly",
        "clean",
        "beautiful",
        "modern",
        "smart",
        "seamless",
        "good",
        "great",
        "friendly",
    ),
    "vague": (
        "fast",
        "quick",
        "quickly",
        "slow",
        "some",
        "several",
        "many",
        "few",
        "approximately",
        "about",
        "significant",
        "flexible",
        "sufficient",
        "efficient",
        "reasonable",
        "stuff",
        "things",
        "various",
        "soon",
        "later on",
    ),
    "escape": (
        "if necessary",
        "as appropriate",
        "where possible",
        "if possible",
        "as required",
        "as needed",
        "so far as is possible",
        "when needed",
    ),
    "open-ended": (
        "etc",
        "and so on",
        "including but not limited to",
        "and more",
        "or something",
        "and stuff",
    ),
    "absolute": ("always", "never", "every", "all", "100%", "everything", "everyone", "nothing"),
    "comparative": ("better", "faster", "easier", "more", "less", "best", "worst"),
    "pronoun": ("it", "they", "them", "this", "that", "these", "those", "something", "someone"),
    "negation": ("not", "no", "without", "none", "nobody"),
}
TERMS = sorted(
    ((term, category) for category, words in LEXICON.items() for term in words),
    key=lambda pair: -len(pair[0]),
)


def scan(text: str) -> list[LexiconFlag]:
    lowered = text.casefold()
    taken: list[tuple[int, int]] = []
    flags: dict[str, tuple[int, LexiconFlag]] = {}
    for term, category in TERMS:
        for match in re.finditer(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered):
            start, end = match.span()
            if any(start < other_end and other_start < end for other_start, other_end in taken):
                continue
            taken.append((start, end))
            flags.setdefault(term, (start, LexiconFlag(word=term, category=category, auto=category in AUTO)))
    return [flag for _, flag in sorted(flags.values(), key=lambda pair: pair[0])]
