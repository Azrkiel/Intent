#!/usr/bin/env python3
"""How well taste-proxies predict the user (Intent skill, Understand step 5).

The user answered yes/no on calibration items (candidate features Intent might add on
its own). Independent proxy subagents, who never saw those answers, predicted them.
This scores the proxies and sets how much Intent may add on its own during Steer.

Usage:
    python proxy_check.py user.json proxies.json
    python proxy_check.py '["yes","no","yes"]' '[["yes","no","no"],["yes","no","yes"],["yes","unsure","yes"]]'

user.json:    a list of "yes" / "no" (or true / false), one per calibration item.
proxies.json: a list of proxies, each a list of "yes" / "no" / "unsure" in the same order.

The prediction for an item is the majority of proxies; ties and "unsure" count as not
yes. The costly error is a false yes: most proxies say "yes" where the user said "no",
because in Steer that is a feature built against the user's wishes.

Verdict:
    trusted    accuracy >= 0.80 and no false yes
    cautious   accuracy >= 0.60 and at most one false yes
    untrusted  anything else
Standard library only.
"""

import json
import sys
from pathlib import Path

TRUSTED_ACCURACY = 0.80
CAUTIOUS_ACCURACY = 0.60


def _answer(value) -> str:
    if value is True or str(value).strip().casefold() in {"yes", "y", "true"}:
        return "yes"
    if value is False or str(value).strip().casefold() in {"no", "n", "false"}:
        return "no"
    return "unsure"


def check(user: list, proxies: list[list]) -> dict:
    if not user or not proxies:
        raise ValueError("Need at least one calibration item and one proxy")
    if any(len(p) != len(user) for p in proxies):
        raise ValueError("Every proxy must answer every calibration item")
    truth = [_answer(u) for u in user]
    if "unsure" in truth:
        raise ValueError("User answers must be yes or no")
    votes = [[_answer(v) for v in p] for p in proxies]
    predicted = []
    for item in range(len(truth)):
        yes = sum(p[item] == "yes" for p in votes)
        predicted.append("yes" if yes * 2 > len(votes) else "no")
    hits = sum(p == t for p, t in zip(predicted, truth))
    accuracy = hits / len(truth)
    false_yes = [i for i, (p, t) in enumerate(zip(predicted, truth)) if p == "yes" and t == "no"]
    if accuracy >= TRUSTED_ACCURACY and not false_yes:
        result = "trusted"
    elif accuracy >= CAUTIOUS_ACCURACY and len(false_yes) <= 1:
        result = "cautious"
    else:
        result = "untrusted"
    return {
        "items": len(truth),
        "proxies": len(votes),
        "accuracy": round(accuracy, 3),
        "false_yes": false_yes,
        "missed": [i for i, (p, t) in enumerate(zip(predicted, truth)) if p != t],
        "per_proxy_accuracy": [
            round(sum(v == t for v, t in zip(p, truth)) / len(truth), 3) for p in votes
        ],
        "verdict": result,
        "budget": {"trusted": "as chosen", "cautious": "at most small", "untrusted": "none"}[result],
    }


def load(value: str):
    path = Path(value)
    return json.loads(path.read_text(encoding="utf-8") if path.is_file() else value)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    print(json.dumps(check(load(argv[0]), load(argv[1])), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
