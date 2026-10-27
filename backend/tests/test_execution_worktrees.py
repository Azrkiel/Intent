import pytest

from backend.app.execution.worktrees import Worktrees


async def test_own_worktree_is_separate_and_survives_cancellation(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    project, checkout = owner.paths("session-test", "run-test")
    base = await owner.create("session-test", "run-test")
    assert len(base) == 40
    assert (checkout / ".git").is_file() and (project / ".git").is_dir()
    (checkout / "result.txt").write_text("preserve")
    assert await owner.changed_paths(checkout) == ["result.txt"]
    assert (checkout / "result.txt").read_text() == "preserve"
    await owner.git(checkout, "add", "result.txt")
    await owner.git(checkout, "commit", "--quiet", "-m", "Synthetic artifact")
    assert await owner.changed_paths(checkout, base) == ["result.txt"]
    (checkout / "result.txt").write_text("tracked change")
    assert await owner.changed_paths(checkout) == ["result.txt"]
    with pytest.raises(ValueError):
        await owner.create("session-test", "run-test")


@pytest.mark.parametrize("id", ["../outside", "C:/outside", "a/b", "a\\b"])
def test_browser_values_cannot_escape_roots(tmp_path, id):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    with pytest.raises(ValueError):
        owner.paths(id, "run-test")


async def test_existing_unowned_project_is_not_reused(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    project, _ = owner.paths("session-test", "run-test")
    project.mkdir(parents=True)
    (project / "user.txt").write_text("preserve")
    with pytest.raises(ValueError):
        await owner.create("session-test", "run-test")
    assert (project / "user.txt").read_text() == "preserve"


async def test_owned_project_supports_independent_workers_at_explicit_base(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    base = await owner.create("session-test", "run-first")
    project, first = owner.paths("session-test", "run-first")
    _, second = owner.paths("session-test", "run-second")
    (first / "first.txt").write_text("unreviewed")
    assert await owner.create("session-test", "run-second", base_commit=base) == base
    assert not (second / "first.txt").exists()
    assert (first / "first.txt").read_text() == "unreviewed"
    assert (project / ".git/intent-owner").read_text() == "session-test"
    assert (await owner.git(second, "rev-parse", "HEAD")).strip() == base


async def test_dirty_project_and_unknown_base_are_preserved(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    base = await owner.create("session-test", "run-first")
    project, _ = owner.paths("session-test", "run-first")
    (project / "untracked.txt").write_text("preserve")
    with pytest.raises(ValueError, match="clean"):
        await owner.create("session-test", "run-second", base_commit=base)
    assert (project / "untracked.txt").read_text() == "preserve"
    (project / "untracked.txt").unlink()
    with pytest.raises(ValueError):
        await owner.create("session-test", "run-second", base_commit="f" * 40)


@pytest.mark.parametrize("identity", ["CON", "NUL", "COM1", "LPT9", ".", "..", "a" * 81])
def test_execution_identities_are_portable(tmp_path, identity):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    with pytest.raises(ValueError):
        owner.paths(identity, "run-test")


def test_rejects_linked_root_and_lexical_traversal(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires OS support/privilege")
    with pytest.raises(ValueError):
        Worktrees(str(linked / "projects"), str(tmp_path / "workers"))
    with pytest.raises(ValueError):
        Worktrees.checked(outside / ".." / "outside" / "file", outside)


async def test_missing_git_preserves_reserved_project(tmp_path, monkeypatch):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    monkeypatch.setenv("PATH", "")
    with pytest.raises(ValueError, match="Git"):
        await owner.create("session-test", "run-test")
    project, _ = owner.paths("session-test", "run-test")
    assert project.exists()
    with pytest.raises(ValueError):
        await owner.create("session-test", "run-test")


async def test_source_checkout_is_never_an_owned_generated_project(tmp_path):
    from pathlib import Path

    source = Path(__file__).resolve().parents[2]
    owner = Worktrees(str(source.parent), str(tmp_path / "workers"))
    with pytest.raises(ValueError, match="source checkout"):
        await owner.owned_project(source.name)


async def test_ignored_files_in_project_root_block_worker_creation(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    base = await owner.create("session-test", "run-first")
    project, _ = owner.paths("session-test", "run-first")
    (project / ".git/info").mkdir(exist_ok=True)
    (project / ".git/info/exclude").write_text("hidden.txt\n")
    (project / "hidden.txt").write_text("unreviewed")
    with pytest.raises(ValueError, match="clean"):
        await owner.create("session-test", "run-second", base_commit=base)


def test_windows_junction_roots_are_rejected(tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junction regression")
    target, link = tmp_path / "outside", tmp_path / "link"
    target.mkdir()
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
    )
    assert result.returncode == 0
    with pytest.raises(ValueError, match="junction"):
        Worktrees(str(link / "projects"), str(tmp_path / "workers"))


async def test_repository_filters_cannot_execute_during_inventory(tmp_path):
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    await owner.create("session-test", "run-test")
    project, checkout = owner.paths("session-test", "run-test")
    (checkout / "result.txt").write_text("original")
    await owner.git(checkout, "add", "result.txt")
    await owner.git(checkout, "commit", "-m", "Synthetic base")
    (project / ".git/info").mkdir(exist_ok=True)
    (project / ".git/info/attributes").write_text("*.txt filter=probe\n")
    marker = tmp_path / "executed.txt"
    with (project / ".git/config").open("a") as stream:
        stream.write('\n[filter "probe"]\n\tclean = echo executed > "' + marker.as_posix() + '"\n')
    (checkout / "result.txt").write_text("changed")
    with pytest.raises(ValueError, match="policy"):
        await owner.changed_paths(checkout)
    assert not marker.exists()


async def test_windows_junction_in_git_object_store_is_rejected(tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junction regression")
    owner = Worktrees(str(tmp_path / "projects"), str(tmp_path / "workers"))
    await owner.create("session-test", "run-test")
    project, _ = owner.paths("session-test", "run-test")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = project / ".git/objects/linked"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True
    )
    assert result.returncode == 0
    with pytest.raises(ValueError, match="junction"):
        await owner.git(project, "rev-parse", "HEAD")
