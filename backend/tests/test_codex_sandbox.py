import os

import pytest

from backend.app.codex import sandbox

windows = pytest.mark.skipif(os.name != "nt", reason="Generated rules apply to Windows workers")


@windows
def test_worker_profile_is_an_allowlist_on_mxc_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "tool_paths", lambda: [])
    project, home = tmp_path / "project", tmp_path / "home"
    arguments = sandbox.app_server_arguments(str(project), str(home))
    assert 'windows.sandbox="mxc"' in arguments
    assert 'default_permissions="intent-worker"' in arguments
    assert "permissions.intent-worker.network.enabled=false" in arguments
    rules = arguments[-1]
    assert rules.startswith('permissions.intent-worker.filesystem={ ":minimal" = "read"')
    assert ":root" not in rules
    assert f'"{project.as_posix()}" = "read"' in rules
    assert f'"{(home / ".sandbox-bin").as_posix()}" = "read"' in rules


@windows
def test_codex_login_is_never_listed_even_though_its_helpers_are(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "tool_paths", lambda: [])
    paths = sandbox.readable_paths(str(tmp_path / "project"), str(tmp_path / "home"))
    assert (tmp_path / "home" / ".sandbox-bin").as_posix() in paths
    assert (tmp_path / "home").as_posix() not in paths


def test_virtualenv_tools_keep_their_base_interpreter(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text(f"home = {tmp_path / 'base'}\n")
    executable = venv / "Scripts" / "python.exe"
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: str(executable) if name == "python" else None)
    assert {venv / "Scripts", venv, tmp_path / "base"} == set(sandbox.tool_paths())


@windows
def test_app_server_refuses_nothing_on_a_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: None)
    assert sandbox.tool_paths() == []
    assert sandbox.app_server_arguments(str(tmp_path / "p"), str(tmp_path / "h"))
