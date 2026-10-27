import asyncio
import json
from pathlib import Path

import pytest

from backend.app.builder import run_build, safe_index
from backend.app.domain import Brief, BriefLine, Session
from backend.app.settings import Settings
from backend.app.store import Store


@pytest.mark.parametrize("is_error,expected", [(False, "complete"), (True, "failed")])
async def test_cli_stream_requires_a_successful_result_even_when_exit_code_is_zero(
    tmp_path,
    monkeypatch,
    is_error,
    expected,
):
    settings = Settings(
        mode="live",
        database_path=str(tmp_path / "db"),
        build_root=str(tmp_path / "builds"),
        allow_claude_build=True,
    )
    session = Session(
        mode="live", brief=Brief(lines=[BriefLine(section="Goal", text="Build a counter", ledger_ids=["L1"])])
    )
    session.build.status = "running"
    store = Store(settings.database_path)
    calls = []
    monkeypatch.setenv("NEBIUS_API_KEY", "must-not-reach-agent")
    monkeypatch.setattr(
        "backend.app.builder.shutil.which", lambda name: "mock-claude" if name == "claude" else None
    )

    class Input:
        def write(self, value):
            assert b"CLAUDE.md" in value

        async def drain(self):
            pass

        def close(self):
            pass

    class Process:
        returncode = 0
        stdin = Input()

        def __init__(self):
            self.stdout = asyncio.StreamReader()
            self.stderr = asyncio.StreamReader()
            result = {"type": "result", "is_error": is_error, "result": "Test result"}
            self.stdout.feed_data((json.dumps(result) + "\n").encode())
            self.stdout.feed_eof()
            self.stderr.feed_eof()

        async def wait(self):
            return self.returncode

    async def fake_spawn(*args, **kwargs):
        calls.append((args, kwargs))
        Path(kwargs["cwd"], "index.html").write_text("<h1>Counter</h1>", encoding="utf-8")
        return Process()

    monkeypatch.setattr("backend.app.builder.asyncio.create_subprocess_exec", fake_spawn)
    await run_build(settings, store, session)
    assert session.build.status == expected
    args, kwargs = calls[0]
    assert "--restricted" in args
    assert "--dangerously-skip-permissions" not in args
    assert "NEBIUS_API_KEY" not in kwargs["env"]
    assert "Bash" not in ",".join(args)
    assert (Path(session.build.directory) / "CLAUDE.md").read_text(encoding="utf-8") == session.brief.markdown


def test_generated_preview_cannot_escape_the_build_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "index.html").write_text("private", encoding="utf-8")
    session = Session()
    session.build.directory = str(outside)
    with pytest.raises(FileNotFoundError):
        safe_index(Settings(build_root=str(tmp_path / "builds")), session)
