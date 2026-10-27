"""Inspect bytes and Git objects without running generated code or repository scripts."""

import hashlib
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from ..planning.validation import overlaps, safe_path

POLICY = "git-inspection-only-v1"
TRUSTED_COMMAND = ["git", "diff", "--check"]


def protected(path):
    return any(
        p.casefold() in {"agents.md", "claude.md", ".codex", ".claude"}
        or p.casefold().startswith(".git")
        or (p.casefold().startswith(".env") and p.casefold() != ".env.example")
        for p in path.split("/")
    )


def redact(text):
    text = re.sub(
        r"(?im)((?:api[_-]?key|token|secret|password|authorization)[\"']?\s*[:=]\s*)[^\r\n]+",
        r"\1[REDACTED]",
        text,
    )
    return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)[:12000]


class Evidence(BaseModel):
    run_id: str
    base_commit: str
    snapshot_commit: str
    changed_paths: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    inventory: dict[str, str] = Field(default_factory=dict)
    checks: list[dict] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    diff: str = ""
    diff_truncated: bool = False
    provenance: str = POLICY
    exclusions: list[str] = Field(default_factory=list)


class VerificationFailure(ValueError):
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence


class Verifier:
    def __init__(self, worktrees):
        self.worktrees = worktrees

    async def checkout(self, run):
        project, checkout = self.worktrees.paths(run.session_id, run.id)
        if (Path(run.project).resolve(), Path(run.worktree).resolve()) != (project, checkout):
            raise ValueError("Saved execution paths differ from owned paths")
        await self.worktrees.owned_project(run.session_id)
        metadata = checkout / ".git"
        self.worktrees.no_links(metadata)
        text = metadata.read_text(encoding="utf-8").strip()
        if not text.startswith("gitdir: "):
            raise ValueError("Worker Git identity is invalid")
        gitdir = Path(text[8:])
        if not gitdir.is_absolute():
            gitdir = checkout / gitdir
        gitdir = self.worktrees.checked(gitdir, project / ".git" / "worktrees")
        backlink = gitdir / "gitdir"
        self.worktrees.no_links(backlink)
        if Path(backlink.read_text(encoding="utf-8").strip()).resolve() != metadata:
            raise ValueError("Worker Git backlink differs from its owned checkout")
        return checkout

    async def tree(self, cwd, commit):
        if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
            raise ValueError("Verification requires an exact saved base commit")
        result = {}
        for record in (await self.worktrees.git(cwd, "ls-tree", "-r", "-z", commit)).split("\0"):
            if not record:
                continue
            info, path = record.split("\t", 1)
            mode, kind, oid = info.split()
            safe_path(path)
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError("Symlinks and submodules require separate inspection policy")
            result[path] = (mode, oid)
        return result

    async def write_tree(self, cwd, files):
        nested = {}
        for path, entry in files.items():
            node = nested
            parts = path.split("/")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
                if not isinstance(node, dict):
                    raise ValueError("File/directory conflict in integration tree")
            if parts[-1] in node:
                raise ValueError("File/directory conflict in integration tree")
            node[parts[-1]] = entry

        async def write(node):
            entries = []
            for name, entry in sorted(node.items()):
                if isinstance(entry, dict):
                    mode, kind, oid = "040000", "tree", await write(entry)
                else:
                    mode, oid = entry
                    kind = "blob"
                entries.append(f"{mode} {kind} {oid}\t{name}\0".encode())
            return (await self.worktrees.git(cwd, "mktree", "-z", input_data=b"".join(entries))).strip()

        return await write(nested)

    async def inspect(self, run, package):
        cwd = await self.checkout(run)
        base = await self.tree(cwd, run.base_commit)
        head = (await self.worktrees.git(cwd, "rev-parse", "HEAD")).strip()
        await self.worktrees.git(cwd, "merge-base", "--is-ancestor", run.base_commit, head)
        tracked = await self.tree(cwd, head)
        candidates = set(base) | set(tracked)
        candidates.update(
            p
            for p in (await self.worktrees.git(cwd, "ls-files", "-z", "--cached", "--others")).split("\0")
            if p
        )
        if len(candidates) > 1024:
            raise ValueError("Artifact inventory exceeds its bound")
        current, hashes, total = {}, {}, 0
        for path in sorted(candidates):
            safe_path(path)
            full = self.worktrees.checked(cwd / path, cwd)
            if not full.exists():
                continue
            if not full.is_file() or full.stat().st_size > 2_000_000:
                raise ValueError("Unsupported or oversized artifact")
            data = full.read_bytes()
            total += len(data)
            if total > 16_000_000:
                raise ValueError("Artifact bytes exceed the inspection allowance")
            mode = (
                ("100755" if full.stat().st_mode & 0o111 else "100644")
                if os.name != "nt"
                else tracked.get(path, ("100644",))[0]
            )
            oid = (
                await self.worktrees.git(cwd, "hash-object", "-w", "--no-filters", "--stdin", input_data=data)
            ).strip()
            current[path] = (mode, oid)
            hashes[path] = hashlib.sha256(data).hexdigest()
        changed = sorted(p for p in set(base) | set(current) if base.get(p) != current.get(p))
        evidence = Evidence(
            run_id=run.id,
            base_commit=run.base_commit,
            snapshot_commit="",
            changed_paths=changed,
            inventory=hashes,
        )
        for path in changed:
            if protected(path) or not any(
                path.casefold() == p.casefold() or path.casefold().startswith(p.casefold() + "/")
                for p in package.owned_paths
            ):
                raise VerificationFailure(
                    "Out-of-scope or protected execution control file blocks integration", evidence
                )
        # No shell, filters, hooks, project tests or generated package scripts are invoked.
        tree = await self.write_tree(cwd, current)
        snapshot = (
            await self.worktrees.git(
                cwd, "commit-tree", tree, "-p", run.base_commit, "-m", "Inspected worker snapshot"
            )
        ).strip()
        evidence.snapshot_commit = snapshot
        diff = await self.worktrees.git(
            cwd, "diff", "--no-ext-diff", "--no-textconv", "--no-color", run.base_commit, snapshot, "--"
        )
        evidence.diff, evidence.diff_truncated = redact(diff), len(diff) > 12000
        for artifact in package.artifacts:
            safe_path(artifact)
            if artifact not in hashes:
                raise VerificationFailure("Required artifact is missing", evidence)
            evidence.artifacts[artifact] = hashes[artifact]
        for task in package.tasks:
            for check in task.checks:
                if check.command != TRUSTED_COMMAND:
                    raise VerificationFailure("Proposed command has no trusted sandbox policy", evidence)
                record = {
                    "argv": TRUSTED_COMMAND,
                    "cwd": "owned-worker-checkout",
                    "policy": POLICY,
                    "environment": "sanitized; Git hooks and external diff disabled",
                    "timeout_seconds": 15,
                    "output_limit_bytes": 2_000_000,
                    "expected": check.expected,
                    "exit_code": 0,
                    "log": "Trusted Git whitespace check passed",
                }
                try:
                    await self.worktrees.git(
                        cwd,
                        "diff",
                        "--check",
                        "--no-ext-diff",
                        "--no-textconv",
                        run.base_commit,
                        snapshot,
                        "--",
                    )
                except ValueError as error:
                    record.update(
                        exit_code=getattr(error, "exit_code", None),
                        log="Trusted Git check failed; generated diagnostic text withheld",
                    )
                    evidence.checks.append(record)
                    raise VerificationFailure("Trusted check failed", evidence) from None
                evidence.checks.append(record)
        evidence.decisions = [s.text for s in package.choices if s.status == "unresolved"]
        evidence.exclusions = [s.text for s in package.exclusions]
        return evidence

    async def integrate(self, run, evidence, expected):
        cwd = await self.checkout(run)
        base = await self.tree(cwd, run.base_commit)
        staged = await self.tree(cwd, expected)
        snapshot = await self.tree(cwd, evidence.snapshot_commit)
        for path in evidence.changed_paths:
            if staged.get(path) != base.get(path):
                raise ValueError(
                    "Integration conflict: staging changed since worker base; preserve both patches"
                )
            if path in snapshot:
                staged[path] = snapshot[path]
            else:
                staged.pop(path, None)
        paths = sorted(staged)
        for i, path in enumerate(paths):
            if any(overlaps(path, other) for other in paths[i + 1 :]):
                raise ValueError("Integration file/directory or case conflict")
        tree = await self.write_tree(cwd, staged)
        return (
            await self.worktrees.git(
                cwd, "commit-tree", tree, "-p", expected, "-m", "Stage verified Intent package"
            )
        ).strip()
