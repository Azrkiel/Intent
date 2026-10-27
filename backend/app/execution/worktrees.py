import asyncio
import os
import re
from pathlib import Path

from ..codex.transport import child_environment


class Worktrees:
    def __init__(self, projects: str, workers: str):
        self.projects, self.workers = Path(projects).absolute(), Path(workers).absolute()
        if (
            self.projects == self.workers
            or self.projects.is_relative_to(self.workers)
            or self.workers.is_relative_to(self.projects)
        ):
            raise ValueError("Project and worker roots must be separate")

    @staticmethod
    def checked(path: Path, root: Path) -> Path:
        for ancestor in [path, *path.parents]:
            if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
                raise ValueError("Worktree roots cannot cross symlinks or junctions")
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
            raise ValueError("Worktree path escaped its owned root")
        return resolved

    def paths(self, session_id: str, run_id: str):
        if any(not re.fullmatch(r"[A-Za-z0-9-]{1,80}", value) for value in (session_id, run_id)):
            raise ValueError("Invalid execution path identity")
        return (
            self.checked(self.projects / session_id, self.projects),
            self.checked(self.workers / run_id, self.workers),
        )

    async def git(self, cwd: Path, *args: str) -> str:
        env = child_environment() | {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        process = await asyncio.create_subprocess_exec(
            "git",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Intent",
            "-c",
            "user.email=intent@localhost",
            *args,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 15)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode or len(output) > 2_000_000:
            raise ValueError("Owned Git operation failed or exceeded its output bound")
        return output.decode("utf-8", errors="strict")

    async def create(self, session_id: str, run_id: str) -> str:
        project, checkout = self.paths(session_id, run_id)
        if checkout.exists():
            raise ValueError("Worker checkout already exists; preserve and reconcile it")
        if project.exists():
            raise ValueError("Existing project needs reviewed integration before another package can run")
        project.mkdir(parents=True)
        checkout.parent.mkdir(parents=True, exist_ok=True)
        await self.git(project, "init", "--quiet", "--template=", "--object-format=sha1")
        (project / ".git" / "intent-owner").write_text(session_id, encoding="utf-8")
        await self.git(project, "commit", "--quiet", "--allow-empty", "-m", "Initialize owned Intent project")
        base = (await self.git(project, "rev-parse", "HEAD")).strip()
        await self.git(project, "worktree", "add", "--quiet", "--detach", str(checkout), base)
        return base

    async def changed_paths(self, checkout: Path, base_commit: str | None = None) -> list[str]:
        raw = await self.git(
            checkout, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"
        )
        changed = {record[3:] for record in raw.split("\0") if record}
        if base_commit:
            committed = await self.git(
                checkout, "diff", "--name-only", "-z", "--no-renames", base_commit, "HEAD"
            )
            changed.update(path for path in committed.split("\0") if path)
        if len(changed) > 1024:
            raise ValueError("Worker change inventory exceeds its bound")
        return sorted(changed)
