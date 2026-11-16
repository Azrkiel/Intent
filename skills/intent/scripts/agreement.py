#!/usr/bin/env python3
"""Reader agreement for a North Star field (Intent skill, check G4).

Two independent readers answer the same multiple-choice probes using only the field
text. Each reader's answers are a JSON list of option indexes (0-based), with -1 for
"cannot tell", in probe order.

Usage:
    python agreement.py reader_a.json reader_b.json [--one-way 0,3]
    python agreement.py '[0,1,1,0,2,0]' '[0,1,1,0,2,1]'

Prints nominal Krippendorff's alpha and a verdict:
    pass      alpha >= 0.80, no "cannot tell", no disagreement on a one-way probe
    follow-up 0.667 <= alpha < 0.80: ask one question about a disagreeing probe
    fail      alpha < 0.667, any "cannot tell", or a one-way probe disagrees

Thresholds follow Krippendorff (0.800 customary, 0.667 lowest acceptable) and match
backend/app/clarity in the Intent repo. Standard library only.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ALPHA_PASS = 0.80
ALPHA_FLOOR = 0.667


def alpha_nominal(first: list[int], second: list[int]) -> float:
    """Krippendorff's alpha for two coders, nominal values, no missing data."""
    if len(first) != len(second) or not first:
        raise ValueError("Reader answers must be non-empty lists of the same length")
    counts = Counter([*first, *second])
    n = 2 * len(first)
    observed = 2 * sum(a != b for a, b in zip(first, second))
    expected = sum(counts[c] * counts[k] for c in counts for k in counts if c != k)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - (observed / n) / (expected / (n * (n - 1)))


def verdict(first: list[int], second: list[int], one_way: set[int] = frozenset()) -> dict:
    alpha = alpha_nominal(first, second)
    disagree = [i for i, (a, b) in enumerate(zip(first, second)) if a != b]
    unclear = [i for i, (a, b) in enumerate(zip(first, second)) if -1 in (a, b)]
    one_way_split = [i for i in disagree if i in one_way]
    if unclear or one_way_split or alpha < ALPHA_FLOOR:
        result = "fail"
    elif alpha < ALPHA_PASS:
        result = "follow-up"
    else:
        result = "pass"
    return {
        "alpha": round(alpha, 3),
        "verdict": result,
        "disagree": disagree,
        "cannot_tell": unclear,
        "one_way_disagree": one_way_split,
    }


def load(value: str) -> list[int]:
    path = Path(value)
    text = path.read_text(encoding="utf-8") if path.is_file() else value
    data = json.loads(text)
    if not isinstance(data, list) or not all(isinstance(x, int) for x in data):
        raise ValueError(f"Expected a JSON list of integers: {value}")
    return data


def main(argv: list[str]) -> int:
    one_way: set[int] = set()
    if "--one-way" in argv:
        index = argv.index("--one-way")
        one_way = {int(x) for x in argv[index + 1].split(",") if x.strip()}
        argv = argv[:index] + argv[index + 2:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    print(json.dumps(verdict(load(argv[0]), load(argv[1]), one_way), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
