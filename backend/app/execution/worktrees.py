import asyncio
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

from ..codex.transport import child_environment
from ..planning.validation import safe_path


class Worktrees:
    def __init__(self, projects: str, workers: str):
        self.projects, self.workers = Path(projects).absolute(), Path(workers).absolute()
        for root in (self.projects, self.workers):
            self.no_links(root)
        self.locks = defaultdict(asyncio.Lock)
        if (
            self.projects == self.workers
            or self.projects.is_relative_to(self.workers)
            or self.workers.is_relative_to(self.projects)
        ):
            raise ValueError("Project and worker roots must be separate")

    @staticmethod
    def no_links(path: Path):
        if ".." in path.parts:
            raise ValueError("Worktree paths cannot contain traversal")
        for ancestor in [path, *path.parents]:
            if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
                raise ValueError("Worktree roots cannot cross symlinks or junctions")

    @classmethod
    def checked(cls, path: Path, root: Path) -> Path:
        cls.no_links(path)
        cls.no_links(root)
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
            raise ValueError("Worktree path escaped its owned root")
        return resolved

    def paths(self, session_id: str, run_id: str):
        if any(not re.fullmatch(r"[A-Za-z0-9-]{1,80}", value) for value in (session_id, run_id)):
            raise ValueError("Invalid execution path identity")
        safe_path(session_id)
        safe_path(run_id)
        return (
            self.checked(self.projects / session_id, self.projects),
            self.checked(self.workers / run_id, self.workers),
        )

    async def git(self, cwd: Path, *args: str) -> str:
        return (await self.git_bytes(cwd, *args)).decode("utf-8", errors="strict")

    async def git_bytes(self, cwd: Path, *args: str) -> bytes:
        self.no_links(cwd)
        executable = shutil.which("git")
        if not executable:
            raise ValueError("Git executable is unavailable")
        env = child_environment() | {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "-c",
                "core.hooksPath=" + os.devnull,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.quotePath=false",
                "-c",
                "diff.external=",
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
        except OSError as error:
            raise ValueError("Owned Git process could not start") from error

        async def read(stream):
            data = bytearray()
            while chunk := await stream.read(65536):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError("Owned Git output exceeds its bound")
            return bytes(data)

        try:
            output, _ = await asyncio.wait_for(asyncio.gather(read(process.stdout), read(process.stderr)), 15)
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError as error:
            raise ValueError("Owned Git operation timed out") from error
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode or len(output) > 2_000_000:
            raise ValueError("Owned Git operation failed or exceeded its output bound")
        return output

    async def owned_project(self, session_id: str) -> Path:
        project, _ = self.paths(session_id, "ownership-check")
        self.no_links(project / ".git")
        marker = project / ".git" / "intent-owner"
        self.no_links(marker)
        if not marker.is_file() or marker.read_text(encoding="utf-8") != session_id:
            raise ValueError("Existing project is not owned by this session")
        if Path((await self.git(project, "rev-parse", "--show-toplevel")).strip()).resolve() != project:
            raise ValueError("Project Git identity does not match its owned path")
        return project

    async def create(self, session_id: str, run_id: str, *, base_commit: str | None = None) -> str:
        async with self.locks[session_id]:
            return await self._create(session_id, run_id, base_commit)

    async def _create(self, session_id: str, run_id: str, base_commit: str | None) -> str:
        project, checkout = self.paths(session_id, run_id)
        if checkout.exists():
            raise ValueError("Worker checkout already exists; preserve and reconcile it")
        checkout.parent.mkdir(parents=True, exist_ok=True)
        if not project.exists():
            project.mkdir(parents=True)
            await self.git(
                project, "init", "--quiet", "--template=", "--object-format=sha1", "--initial-branch=accepted"
            )
            (project / ".git" / "intent-owner").write_text(session_id, encoding="utf-8")
            await self.git(
                project, "commit", "--quiet", "--allow-empty", "-m", "Initialize owned Intent project"
            )
        await self.owned_project(session_id)
        if await self.git(project, "status", "--porcelain=v1", "--untracked-files=all"):
            raise ValueError("Owned project must be clean; preserve dirty or untracked work")
        if base_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            raise ValueError("Worker base must be an exact commit")
        base = (
            await self.git(project, "rev-parse", "--verify", (base_commit or "HEAD") + "^{commit}")
        ).strip()
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
