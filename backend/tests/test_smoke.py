import json

import pytest
from pydantic import SecretStr

from backend import smoke
from backend.app.domain import Critique, Delta, Usage
from backend.app.models import ModelError
from backend.app.settings import Settings


async def test_missing_key_writes_failure_without_creating_a_provider(tmp_path, monkeypatch):
    config = Settings(_env_file=None, NEBIUS_API_KEY=None)
    monkeypatch.setattr(smoke, "Settings", lambda **kwargs: config)

    def forbidden_factory(settings):
        pytest.fail("A missing key must make zero requests")

    output = tmp_path / "missing.json"
    with pytest.raises(SystemExit) as error:
        await smoke.run(False, output, provider_factory=forbidden_factory)
    assert error.value.code == 1
    report = json.loads(output.read_text())
    assert not report["passed"]
    assert report["results"][0]["failure"] == "missing_credentials"
    assert report["results"][0]["usage"] == []


async def test_failed_probes_preserve_usage_and_close_clients(tmp_path, monkeypatch, capsys):
    config = Settings(_env_file=None, NEBIUS_API_KEY=SecretStr("test-only"))
    monkeypatch.setattr(smoke, "Settings", lambda **kwargs: config)
    closed = []

    class FailingProvider:
        def __init__(self, settings):
            self.model = settings.nano_model

        async def call(self, session, role, schema, instruction, payload):
            session.usage.append(
                Usage(
                    role=role,
                    model=self.model,
                    input_tokens=20,
                    output_tokens=10,
                    estimated_usd=0.000004,
                    latency_ms=100,
                )
            )
            raise ModelError("Invalid JSON after repair: test-only")

        async def close(self):
            closed.append(self.model)

    output = tmp_path / "failed.json"
    with pytest.raises(SystemExit) as error:
        await smoke.run(False, output, provider_factory=FailingProvider)
    assert error.value.code == 1
    report = json.loads(output.read_text())
    assert closed == [config.nano_model, "nvidia/Nemotron-3_5-Lightning"]
    assert len(report["results"]) == 2
    assert sum(len(item["usage"]) for item in report["results"]) == 2
    assert all(item["failure"] == "model_error" for item in report["results"])
    assert not report["passed"]
    assert "test-only" not in output.read_text()
    assert "test-only" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "case,passed,failure",
    [
        ("grounded", True, None),
        ("empty", False, "model_error"),
        ("unquoted", False, "model_error"),
        ("unknown_update", False, "ledger_validation"),
        ("no_question", False, "model_error"),
        ("empty_targets", False, "model_error"),
        ("unknown_target", False, "model_error"),
        ("wrong_lens", False, "model_error"),
        ("no_divergence", False, "model_error"),
    ],
)
async def test_probes_require_grounded_extraction_and_useful_critique(
    tmp_path,
    monkeypatch,
    case,
    passed,
    failure,
):
    config = Settings(_env_file=None, NEBIUS_API_KEY=SecretStr("test-only"))
    monkeypatch.setattr(smoke, "Settings", lambda **kwargs: config)
    closed, calls = [], []

    class Provider:
        def __init__(self, settings):
            self.model = settings.nano_model

        async def call(self, session, role, schema, instruction, payload):
            calls.append((self.model, role))
            session.usage.append(
                Usage(
                    role=role,
                    model=self.model if role == "extractor" else config.super_model,
                    input_tokens=20,
                    output_tokens=10,
                    estimated_usd=0.000004,
                    latency_ms=100,
                )
            )
            if role == "extractor":
                if case == "empty":
                    return Delta()
                if case == "unknown_update":
                    return Delta(update=[{"id": "L99", "text": "Unknown"}])
                return Delta(
                    add=[
                        {
                            "type": "goal",
                            "text": "Build a habit tracker",
                            "status": "confirmed",
                            "source": "Invented source" if case == "unquoted" else "I want a habit tracker",
                        }
                    ]
                )
            question = dict(
                lens="data" if case == "wrong_lens" else "contradictions",
                targets=[] if case == "empty_targets" else ["L99" if case == "unknown_target" else "L1"],
                question="How should phone and laptop share habits without login?",
                options=["Use a shared secret link", "Keep separate local data"],
                code_diff="Shared server storage versus separate browser stores.",
                divergence=1 if case == "no_divergence" else 3,
                uncertainty=3,
                cost_to_change=3,
            )
            return Critique(candidates=[] if case == "no_question" else [question])

        async def close(self):
            closed.append(self.model)

    output = tmp_path / "report.json"
    if passed:
        await smoke.run(False, output, provider_factory=Provider)
    else:
        with pytest.raises(SystemExit) as error:
            await smoke.run(False, output, provider_factory=Provider)
        assert error.value.code == 1
    report = json.loads(output.read_text())
    assert report["passed"] is passed
    assert report["results"][0]["failure"] == failure
    assert closed == [config.nano_model, "nvidia/Nemotron-3_5-Lightning"]
    assert [role for _, role in calls].count("critic:contradictions") == (
        0 if case in {"empty", "unquoted", "unknown_update"} else 1
    )
    assert sum(len(item["usage"]) for item in report["results"]) == len(calls)
    # A failed Nano critic must not prevent the independent Lightning extraction.
    assert report["results"][1]["passed"] is (case not in {"empty", "unquoted", "unknown_update"})
