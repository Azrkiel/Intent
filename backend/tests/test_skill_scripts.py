"""The Intent skill's standalone scripts must stay in step with the app they were copied from."""

import importlib.util
import random
from pathlib import Path

from backend.app.clarity import lexicon as app_lexicon
from backend.app.clarity.contracts import Thresholds
from backend.app.clarity.northstar import alpha_nominal

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "intent" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"intent_skill_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_lexicon_matches_app():
    skill = load("lexicon")
    assert skill.LEXICON == app_lexicon.LEXICON
    assert skill.AUTO == app_lexicon.AUTO
    assert skill.LEXICON_VERSION == app_lexicon.LEXICON_VERSION
    for text in ("find stuff fast and easy, etc", "it always works if possible and is not slow"):
        assert [(f["word"], f["category"], f["auto"]) for f in skill.scan(text)] == [
            (f.word, f.category, f.auto) for f in app_lexicon.scan(text)
        ]


def test_skill_agreement_matches_app():
    skill = load("agreement")
    defaults = Thresholds()
    assert (skill.ALPHA_PASS, skill.ALPHA_FLOOR) == (defaults.alpha_pass, defaults.alpha_floor)
    rng = random.Random(7)
    for _ in range(200):
        size = rng.randint(2, 8)
        first = [rng.randint(-1, 2) for _ in range(size)]
        second = [rng.randint(-1, 2) for _ in range(size)]
        assert skill.alpha_nominal(first, second) == alpha_nominal(first, second)


def test_skill_agreement_verdicts():
    skill = load("agreement")
    assert skill.verdict([0, 1, 1, 0, 2, 0], [0, 1, 1, 0, 2, 0])["verdict"] == "pass"
    assert skill.verdict([0, 1, 1, 0, 2, 0], [0, 1, -1, 0, 2, 0])["verdict"] == "fail"
    assert skill.verdict([0, 1, 1, 0, 2, 0], [1, 1, 1, 0, 2, 0], {0})["verdict"] == "fail"
