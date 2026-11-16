#!/usr/bin/env python3
"""Flag vague wording in a requirement (Intent skill, check G1).

Usage:
    python lexicon.py "find an article fast, etc"
    echo "text" | python lexicon.py
    python lexicon.py --json "text"

Word lists follow INCOSE GtWR rules R7-R9 and R26 and the requirement smells of
Femmer et al. (2017). They are copied from backend/app/clarity/lexicon.py in the Intent
repo; keep the two in sync. Standard library only.

Categories marked auto are reliable enough to prompt the user directly. The rest
(absolute, comparative, pronoun, negation) often misfire: decide first whether the word
really leaves doubt about what to build.
"""

import json
import re
import sys

LEXICON_VERSION = "2026-10-29.1"
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


def scan(text: str) -> list[dict]:
    """Return flags in reading order: word, category and whether to prompt automatically."""
    lowered = text.casefold()
    taken: list[tuple[int, int]] = []
    flags: dict[str, tuple[int, dict]] = {}
    for term, category in TERMS:
        for match in re.finditer(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered):
            start, end = match.span()
            if any(start < other_end and other_start < end for other_start, other_end in taken):
                continue
            taken.append((start, end))
            flags.setdefault(term, (start, {"word": term, "category": category, "auto": category in AUTO}))
    return [flag for _, flag in sorted(flags.values(), key=lambda pair: pair[0])]


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [arg for arg in argv if arg != "--json"]
    text = " ".join(args) if args else sys.stdin.read()
    flags = scan(text)
    if as_json:
        print(json.dumps({"version": LEXICON_VERSION, "flags": flags}, indent=2))
        return 0
    if not flags:
        print("No vague words flagged.")
        return 0
    for flag in flags:
        action = "prompt once" if flag["auto"] else "judge first"
        print(f'"{flag["word"]}"  {flag["category"]}  ({action})')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
