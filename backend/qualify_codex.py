"""Check the configured managed profile, optionally dispatch one explicitly selected phase."""

import argparse
import asyncio
import inspect
import json
import os
import shutil
from pathlib import Path

from backend.app.codex.client import Client
from backend.app.codex.protocol import CodexError
from backend.app.codex.transport import Transport
from backend.app.execution.worker import Executor
from backend.app.settings import Settings
from backend.app.store import Store
from backend.qualification_report import write_report


async def configured_client(config):
    executable = shutil.which(config.codex_command)
    if not executable:
        raise CodexError("Configured executable unavailable")
    home = config.codex_home or os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    transport = Transport([executable, "app-server"], cwd=str(Path.cwd()), home=home)
    try:
        await transport.start()
    except BaseException:
        await transport.close()
        raise
    return Client(transport, config.codex_approval_timeout_seconds)


async def run(output, *, session_id=None, phase_id=None, settings=None, factory=configured_client):
    record = {"failure": "execution_disabled"}
    client, executor = None, None
    try:
        config = settings or Settings(mode="live")
        if not config.allow_codex_execution:
            print("No model requests: ALLOW_CODEX_EXECUTION is disabled.")
        else:
            print("No model requests during profile check; managed account and model inventory reads only.")
            record["failure"] = "profile_unavailable"
            candidate = factory(config)
            client = await candidate if inspect.isawaitable(candidate) else candidate
            profile = await client.qualify(str(Path.cwd()))
            record.update(
                profile_qualified=True, selected_model=profile["model"], failure="approved_session_required"
            )
            if session_id and phase_id:
                store = Store(config.database_path)
                session = store.get(session_id)
                executor = Executor(config, store)
                identity = session.planning.approval
                executor.guard(session, identity)
                # Existing outcomes are inspected, never redispatched by this command.
                try:
                    phase = executor.runs.phase(session.id, identity.content_hash, phase_id)
                except KeyError:
                    print(
                        "Selected phase: only reviewed contexts can dispatch. "
                        "No automatic context or permission grants."
                    )
                    phase = executor.start_phase(session, identity, phase_id)
                    await executor.phase_tasks[phase.id]
                    phase = executor.runs.phase(session.id, identity.content_hash, phase_id)
                    record["model_requests_possible"] = bool(executor.phase_runs(phase))
                runs = executor.phase_runs(phase)
                record["codex_tokens"] = {
                    key: sum(r.token_usage.get(key, 0) for r in runs)
                    for key in ("inputTokens", "outputTokens", "totalTokens", "cachedInputTokens")
                }
                passed = phase.status in {"awaiting_phase_review", "accepted"} and bool(runs)
                awaiting_context = phase.status == "awaiting_context_review"
                record.update(
                    automated_checks_passed=passed,
                    failure="context_review_required"
                    if awaiting_context
                    else "phase_review_required"
                    if passed
                    else "execution_failed",
                    status="incomplete" if passed or awaiting_context else "failed",
                )
    except Exception:
        record.update(status="failed", failure=("execution_failed" if executor else "profile_unavailable"))
    finally:
        for resource in (executor, client):
            if resource:
                try:
                    await resource.close()
                except Exception:
                    record.update(status="failed", failure="cleanup_failed")
    return write_report(output, "codex_integration_not_quality_evaluation", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".data/live-check/codex.json")
    parser.add_argument("--session-id", help="Existing approved live plan; stop the app server first")
    parser.add_argument("--phase-id", help="Explicit phase to dispatch once, or inspect if already attempted")
    args = parser.parse_args()
    report = asyncio.run(run(args.output, session_id=args.session_id, phase_id=args.phase_id))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["automated_checks_passed"] else 1)


if __name__ == "__main__":
    main()
