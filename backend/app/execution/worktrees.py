import asyncio
import configparser
import hashlib
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

from ..codex.transport import child_environment
from ..planning.validation import safe_path


class GitFailure(ValueError):
    def __init__(self, exit_code):
        super().__init__("Owned Git operation failed; generated diagnostics withheld")
        self.exit_code = exit_code


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

    async def git(self, cwd: Path, *args: str, input_data: bytes | None = None) -> str:
        return (await self.git_bytes(cwd, *args, input_data=input_data)).decode("utf-8", errors="strict")

    async def git_bytes(self, cwd: Path, *args: str, input_data: bytes | None = None) -> bytes:
        self.no_links(cwd)
        self.check_policy(cwd)
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
                "core.longpaths=true",
                "-c",
                "core.quotePath=false",
                "-c",
                "core.attributesFile=" + os.devnull,
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
                stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL,
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
            if input_data is not None:
                process.stdin.write(input_data)
                await asyncio.wait_for(process.stdin.drain(), 15)
                process.stdin.close()
            output, _ = await asyncio.wait_for(asyncio.gather(read(process.stdout), read(process.stderr)), 15)
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError as error:
            raise ValueError("Owned Git operation timed out") from error
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode:
            raise GitFailure(process.returncode)
        return output

    def check_policy(self, cwd: Path):
        cwd = cwd.resolve()
        if cwd.is_relative_to(self.projects):
            parts = cwd.relative_to(self.projects).parts
            if not parts:
                raise ValueError("Git policy requires an owned project")
            common = self.projects / parts[0] / ".git"
        elif cwd.is_relative_to(self.workers):
            metadata = cwd / ".git"
            self.no_links(metadata)
            text = metadata.read_text(encoding="utf-8").strip()
            if not text.startswith("gitdir: "):
                raise ValueError("Git policy requires owned worktree metadata")
            gitdir = Path(text[8:])
            if not gitdir.is_absolute():
                gitdir = cwd / gitdir
            self.no_links(gitdir)
            common_file = gitdir / "commondir"
            self.no_links(common_file)
            common = (gitdir / common_file.read_text(encoding="utf-8").strip()).resolve()
            if common.name != ".git" or not common.is_relative_to(self.projects):
                raise ValueError("Git policy rejects external common directories")
        else:
            raise ValueError("Git policy rejects paths outside owned roots")
        self.no_links(common)
        config = common / "config"
        self.no_links(config)
        if config.exists():
            parser = configparser.RawConfigParser()
            try:
                parser.read_string(config.read_text(encoding="utf-8"))
            except (configparser.Error, UnicodeError) as error:
                raise ValueError("Git policy rejects malformed repository configuration") from error
            allowed = {
                "repositoryformatversion",
                "filemode",
                "bare",
                "logallrefupdates",
                "symlinks",
                "ignorecase",
            }
            if (
                parser.defaults()
                or set(parser.sections()) != {"core"}
                or not set(parser["core"]) <= allowed
                or parser["core"].get("bare") != "false"
            ):
                raise ValueError(
                    "Git policy rejects repository filters, includes, tools and config overrides"
                )
        for path in (common / "info/attributes", common / "objects/info/alternates"):
            self.no_links(path)
            if path.exists():
                raise ValueError("Git policy rejects repository attributes and external object stores")
        pending, count = [common], 0
        while pending:
            directory = pending.pop()
            if not directory.exists():
                continue
            for entry in directory.iterdir():
                count += 1
                if count > 16384:
                    raise ValueError("Git metadata inspection exceeds its policy bound")
                if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
                    raise ValueError("Git metadata policy rejects symlinks and junctions")
                if entry.is_dir():
                    pending.append(entry)

    async def owned_project(self, session_id: str) -> Path:
        project, _ = self.paths(session_id, "ownership-check")
        if project == Path(__file__).resolve().parents[3]:
            raise ValueError("The Intent source checkout cannot be a generated project")
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
        if await self.changed_paths(project):
            raise ValueError("Owned project must be clean; preserve dirty or untracked work")
        if base_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            raise ValueError("Worker base must be an exact commit")
        base = (
            await self.git(project, "rev-parse", "--verify", (base_commit or "HEAD") + "^{commit}")
        ).strip()
        await self.git(
            project, "worktree", "add", "--quiet", "--detach", "--no-checkout", str(checkout), base
        )
        # Materialize raw blobs ourselves: checkout/smudge filters are never executed.
        for record in (await self.git(project, "ls-tree", "-r", "-z", base)).split("\0"):
            if not record:
                continue
            info, path = record.split("\t", 1)
            mode, kind, oid = info.split()
            safe_path(path)
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError("Git policy rejects symlinks and submodules in checkout trees")
            target = self.checked(checkout / path, checkout)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(await self.git_bytes(project, "cat-file", "blob", oid))
            if os.name != "nt" and mode == "100755":
                target.chmod(0o755)
        await self.git(checkout, "read-tree", base)
        return base

    async def changed_paths(self, checkout: Path, base_commit: str | None = None) -> list[str]:
        tracked = {}
        for record in (await self.git(checkout, "ls-tree", "-r", "-z", "HEAD")).split("\0"):
            if record:
                info, path = record.split("\t", 1)
                mode, kind, oid = info.split()
                if kind != "blob" or mode not in {"100644", "100755"}:
                    raise ValueError("Git policy rejects symlinks and submodules")
                tracked[path] = (mode, oid)
        changed = set()
        candidates = set(tracked) | {
            p for p in (await self.git(checkout, "ls-files", "--others", "--cached", "-z")).split("\0") if p
        }
        if len(candidates) > 1024:
            raise ValueError("Worker change inventory exceeds its bound")
        for path in candidates:
            safe_path(path)
            full = self.checked(checkout / path, checkout)
            if not full.exists():
                changed.add(path)
                continue
            if not full.is_file() or full.stat().st_size > 2_000_000:
                raise ValueError("Unsupported or oversized worker artifact")
            data = full.read_bytes()
            oid = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            mode = (
                ("100755" if full.stat().st_mode & 0o111 else "100644")
                if os.name != "nt"
                else tracked.get(path, ("100644",))[0]
            )
            if tracked.get(path) != (mode, oid):
                changed.add(path)
        if base_commit:
            committed = await self.git(
                checkout,
                "diff",
                "--name-only",
                "-z",
                "--no-renames",
                "--no-ext-diff",
                "--no-textconv",
                base_commit,
                "HEAD",
            )
            changed.update(path for path in committed.split("\0") if path)
        others = await self.git(checkout, "ls-files", "--others", "-z")
        changed.update(path for path in others.split("\0") if path)
        if len(changed) > 1024:
            raise ValueError("Worker change inventory exceeds its bound")
        return sorted(changed)
