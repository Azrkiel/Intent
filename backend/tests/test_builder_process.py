"""Real subprocess I/O with a local scripted agent; no Claude/model calls."""

import asyncio
import sys
import textwrap

import pytest

from backend.app.builder import run_build
from backend.app.domain import Brief, BriefLine, Session
from backend.app.settings import Settings
from backend.app.store import Store


@pytest.fixture
def local_agent(tmp_path, monkeypatch):
    script = tmp_path / "agent.py"
    script.write_text(
        textwrap.dedent("""\
        import json
        import os
        from pathlib import Path
        import sys
        import time

        scenario = sys.argv[1]
        prompt = sys.stdin.read()
        assert "CLAUDE.md" in prompt
        assert "NEBIUS_API_KEY" not in os.environ
        assert "TOKEN_FACTORY_API_KEY" not in os.environ
        assert "OPENAI_API_KEY" not in os.environ
        assert "CLAUDECODE" not in os.environ
        assert Path("CLAUDE.md").is_file()
        if scenario == "hang":
            time.sleep(60)
        if scenario != "no_index":
            Path("index.html").write_text("<h1>Offline subprocess fixture</h1>", encoding="utf-8")
        print("non-JSON diagnostic", flush=True)
        print(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Scripted local agent"},
            {"type": "tool_use", "name": "Write"}
        ]}}), flush=True)
        # More than a pipe buffer: the adapter must drain stderr concurrently.
        for _ in range(150):
            print("stderr fixture " + "x" * 1000, file=sys.stderr)
        if scenario != "missing_result":
            print(json.dumps({"type": "result", "is_error": scenario == "error_result",
                              "result": "Offline test finished"}), flush=True)
        sys.exit(1 if scenario == "nonzero_exit" else 0)
    """),
        encoding="utf-8",
    )
    real_spawn = asyncio.create_subprocess_exec
    processes = []
    scenario = ["success"]

    async def spawn(*args, **kwargs):
        process = await real_spawn(sys.executable, "-u", str(script), scenario[0], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(
        "backend.app.builder.shutil.which", lambda name: sys.executable if name == "claude" else None
    )
    monkeypatch.setattr("backend.app.builder.asyncio.create_subprocess_exec", spawn)
    for name in ["NEBIUS_API_KEY", "TOKEN_FACTORY_API_KEY", "OPENAI_API_KEY", "CLAUDECODE"]:
        monkeypatch.setenv(name, "offline-test-secret")
    settings = Settings(
        _env_file=None, mode="live", database_path=str(tmp_path / "db"), build_root=str(tmp_path / "builds")
    )
    session = Session(
        mode="live",
        brief=Brief(
            lines=[
                BriefLine(section="Goal", text="An offline subprocess fixture", ledger_ids=["L1"]),
            ]
        ),
    )
    session.build.status = "running"
    return settings, Store(settings.database_path), session, scenario, processes


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("success", "complete"),
        ("missing_result", "failed"),
        ("error_result", "failed"),
        ("nonzero_exit", "failed"),
        ("no_index", "failed"),
    ],
)
async def test_real_subprocess_requires_result_exit_and_artifact(local_agent, scenario, expected):
    settings, store, session, choice, processes = local_agent
    choice[0] = scenario
    await asyncio.wait_for(run_build(settings, store, session), timeout=15)
    assert session.build.status == expected
    assert store.get(session.id).build.status == expected
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert len(session.build.logs) <= 160
    assert all(len(line) <= 2000 for line in session.build.logs)
    assert not any("offline-test-secret" in line for line in session.build.logs)
    assert any("Scripted local agent" in line for line in session.build.logs)
    assert bool(session.build.preview_url) is (expected == "complete")


async def test_timed_out_process_is_killed_and_failure_is_persisted(local_agent):
    settings, store, session, choice, processes = local_agent
    choice[0] = "hang"
    # Use a short deadline in this test; the normal setting has a 10-second minimum.
    settings = settings.model_copy(update={"build_timeout_seconds": 0.5})
    await asyncio.wait_for(run_build(settings, store, session), timeout=5)
    assert processes[0].returncode is not None
    assert store.get(session.id).build.status == "failed"
    assert "Build timed out." in session.build.logs


async def test_cancellation_kills_the_agent_and_persists_failure(local_agent):
    settings, store, session, choice, processes = local_agent
    choice[0] = "hang"
    task = asyncio.create_task(run_build(settings, store, session))
    try:
        async with asyncio.timeout(5):
            while not processes:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert processes[0].returncode is not None
    assert store.get(session.id).build.status == "failed"
    assert "Build stopped because the server is shutting down." in session.build.logs
