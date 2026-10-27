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
