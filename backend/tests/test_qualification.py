import json

import pytest
from pydantic import SecretStr

from backend.app.demo import DemoModels
from backend.app.domain import Usage
from backend.app.models import ModelError
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session


def settings(tmp_path, **changes):
    return Settings(
        _env_file=None,
        mode="live",
        nebius_api_key=None,
        database_path=str(tmp_path / "sessions.db"),
        **changes,
    )


@pytest.mark.parametrize("module", ["qualify_planning", "qualify_codex"])
async def test_missing_prerequisites_make_no_requests(tmp_path, module, capsys):
    from importlib import import_module

    qualifier = import_module(f"backend.{module}")

    def forbidden(*args):
        pytest.fail("Missing prerequisites must not construct a provider")

    output = tmp_path / "report.json"
    result = await qualifier.run(output, settings=settings(tmp_path), factory=forbidden)
    assert result["status"] == "incomplete"
    assert result["failure"] == (
        "missing_credentials" if module == "qualify_planning" else "execution_disabled"
    )
    assert not result["passed"] and not result["model_requests_possible"]
    assert "No model requests" in capsys.readouterr().out
    assert json.loads(output.read_text()) == result


async def test_planning_failure_retains_usage_and_allowance_without_leaking(tmp_path, capsys):
    from backend.qualify_planning import run

    config = settings(tmp_path).model_copy(update={"nebius_api_key": SecretStr("unused-in-fake")})
    store = Store(config.database_path)
    session = ready_session()
    session.mode = "live"
    store.save(session)

    class Failing:
        closed = False

        async def call(self, current, *args):
            current.usage.append(
                Usage(
                    role="planner:outline",
                    model="nvidia/nemotron-3-super-120b-a12b",
                    input_tokens=12,
                    output_tokens=7,
                    latency_ms=19,
                    estimated_usd=0.01,
                )
            )
            raise ModelError("SECRET account@example.org transcript auth payload")

        async def close(self):
            self.closed = True

    provider = Failing()
    output = tmp_path / "report.json"
    result = await run(output, session_id=session.id, settings=config, factory=lambda _: provider)
    assert result["status"] == "failed" and result["failure"] == "planning_failed"
    assert result["usage"][0]["input_tokens"] == 12
    assert len(store.get(session.id).planning.attempts) == 1
    assert provider.closed
    assert "SECRET" not in output.read_text() + capsys.readouterr().out


async def test_planning_preserves_review_gate_and_exports_only_after_approval(tmp_path):
    from backend.qualify_planning import run

    config = settings(tmp_path).model_copy(update={"nebius_api_key": SecretStr("fake")})
    store = Store(config.database_path)
    session = ready_session()
    session.mode = "live"
    store.save(session)

    class Offline(DemoModels):
        async def close(self):
            pass

    output = tmp_path / "report.json"
    result = await run(output, session_id=session.id, settings=config, factory=lambda _: Offline())
    assert result["automated_checks_passed"]
    assert not result["passed"] and result["failure"] == "plan_review_required"
    assert not (tmp_path / "planning-bundle.zip").exists()
    current = store.get(session.id)
    assert current.planning.approval is None
    current.planning.approval = current.planning.active
    current.planning.status = "approved"
    store.save(current)
    result = await run(output, session_id=session.id, settings=config, factory=lambda _: Offline())
    assert result["failure"] == "manual_audit_required"
    assert not result["model_requests_possible"]
    assert (tmp_path / "planning-bundle.zip").exists()
    assert len(store.get(session.id).planning.attempts) == 1


async def test_codex_checks_managed_profile_without_dispatch(tmp_path):
    from backend.qualify_codex import run

    class Profile:
        closed = False

        async def qualify(self, cwd):
            return {"type": "chatgpt", "model": "gpt-5.3-codex", "email": "SECRET"}

        async def close(self):
            self.closed = True

    profile = Profile()
    config = settings(tmp_path, allow_codex_execution=True)
    result = await run(tmp_path / "report.json", settings=config, factory=lambda _: profile)
    assert result["failure"] == "approved_session_required"
    assert result["profile_qualified"]
    assert not result["model_requests_possible"]
    assert profile.closed
    assert "SECRET" not in json.dumps(result)


async def test_codex_profile_failure_is_redacted_and_closed(tmp_path):
    from backend.qualify_codex import run

    class Profile:
        closed = False

        async def qualify(self, cwd):
            raise RuntimeError("SECRET account payload")

        async def close(self):
            self.closed = True

    profile = Profile()
    result = await run(
        tmp_path / "report.json",
        settings=settings(tmp_path, allow_codex_execution=True),
        factory=lambda _: profile,
    )
    assert result["failure"] == "profile_unavailable"
    assert profile.closed and "SECRET" not in json.dumps(result)


def test_report_drops_sensitive_fields_even_nested_in_usage(tmp_path):
    from backend.qualification_report import write_report

    report = write_report(
        tmp_path / "report.json",
        "planning",
        {
            "failure": "SECRET",
            "account": "SECRET",
            "error": "SECRET",
            "transcript": "SECRET",
            "usage": [
                {
                    "role": "SECRET",
                    "model": "SECRET",
                    "input_tokens": 8,
                    "output_tokens": 3,
                    "estimated_usd": 0.02,
                    "latency_ms": 5,
                    "auth": "SECRET",
                }
            ],
        },
    )
    assert "SECRET" not in json.dumps(report)
    assert report["usage"][0]["input_tokens"] == 8
    assert not report["passed"]


@pytest.mark.parametrize("approved,mode", [(False, "live"), (True, "demo")])
async def test_planning_rejects_unapproved_or_demo_session_before_provider(tmp_path, approved, mode):
    from backend.qualify_planning import run

    config = settings(tmp_path).model_copy(update={"nebius_api_key": SecretStr("fake")})
    store = Store(config.database_path)
    session = ready_session()
    session.mode = mode
    session.approved_revision = 1 if approved else None
    store.save(session)

    def forbidden(*args):
        pytest.fail("Unapproved or demo session cannot construct a live provider")

    result = await run(tmp_path / "report.json", session_id=session.id, settings=config, factory=forbidden)
    assert not result["model_requests_possible"]
    assert result["status"] == "failed"


@pytest.mark.parametrize("scenario,success", [("scoped_artifact", True), ("out_of_scope", False)])
async def test_codex_evidence_and_repeat_do_not_redispatch(tmp_path, monkeypatch, scenario, success):
    from backend import qualify_codex
    from backend.tests.test_codex_worker import approve_package
    from backend.tests.test_execution_verification import scoped_fixture

    session, document, executor = scoped_fixture(tmp_path, scenario)
    executor.scheduler.capacity = 2
    await approve_package(session, document, executor, "P1-W1")
    await approve_package(session, document, executor, "P1-W2")
    monkeypatch.setattr(qualify_codex, "Executor", lambda *args: executor)

    class Profile:
        async def qualify(self, cwd):
            return {"model": "gpt-5.3-codex"}

        async def close(self):
            pass

    output = tmp_path / "codex.json"
    result = await qualify_codex.run(
        output, session_id=session.id, phase_id="P1", settings=executor.settings, factory=lambda _: Profile()
    )
    assert result["automated_checks_passed"] is success
    assert not result["passed"]
    runs = executor.runs.list(session.id)
    assert runs
    again = await qualify_codex.run(
        output, session_id=session.id, phase_id="P1", settings=executor.settings, factory=lambda _: Profile()
    )
    assert not again["model_requests_possible"]
    assert [r.id for r in executor.runs.list(session.id)] == [r.id for r in runs]
    phase = executor.runs.phase(session.id, session.planning.approval.content_hash, "P1")
    assert phase.status != "accepted"


async def test_codex_qualifier_preserves_context_review_pause_without_dispatch(tmp_path, monkeypatch):
    from backend import qualify_codex
    from backend.tests.test_execution_verification import scoped_fixture

    session, _, executor = scoped_fixture(tmp_path, "scoped_artifact")
    monkeypatch.setattr(qualify_codex, "Executor", lambda *args: executor)

    async def forbidden(run):
        pytest.fail("Missing context approval cannot start a worker process")

    executor.factory = forbidden

    class Profile:
        async def qualify(self, cwd):
            return {"model": "gpt-5.3-codex"}

        async def close(self):
            pass

    result = await qualify_codex.run(
        tmp_path / "codex-context.json",
        session_id=session.id,
        phase_id="P1",
        settings=executor.settings,
        factory=lambda _: Profile(),
    )
    assert result["status"] == "incomplete"
    assert result["failure"] == "context_review_required"
    assert not result["automated_checks_passed"] and not result["model_requests_possible"]
    assert not executor.runs.list(session.id)
    assert (
        executor.runs.phase(session.id, session.planning.approval.content_hash, "P1").status
        == "awaiting_context_review"
    )


async def test_planning_cleanup_failure_cannot_exit_as_success(tmp_path):
    from backend.qualify_planning import run

    config = settings(tmp_path).model_copy(update={"nebius_api_key": SecretStr("fake")})
    store = Store(config.database_path)
    session = ready_session()
    session.mode = "live"
    store.save(session)

    class Offline(DemoModels):
        async def close(self):
            raise RuntimeError("SECRET")

    result = await run(
        tmp_path / "report.json", session_id=session.id, settings=config, factory=lambda _: Offline()
    )
    assert result["status"] == "failed" and not result["automated_checks_passed"]
