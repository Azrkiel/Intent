"""Deterministic review identity and explicit lifecycle transitions."""

import hashlib
import json

from .contracts import PhaseReview
from .verification import POLICY, TRUSTED_COMMAND


def transition(kind, before, after):
    edges = {
        "run": {("queued", "running"), ("running", "verifying"), ("verifying", "integrated")},
        "phase": {
            ("running", "awaiting_context_review"),
            ("awaiting_context_review", "running"),
            ("running", "verifying"),
            ("verifying", "awaiting_phase_review"),
            ("awaiting_phase_review", "accepted"),
        },
        "plan": {
            ("draft", "planning"),
            ("planning", "review_ready"),
            ("review_ready", "approved"),
            ("blocked", "planning"),
        },
    }
    terminal = {
        "run": {"integrated", "blocked", "cancelled"},
        "phase": {"accepted", "blocked", "cancelled"},
        "plan": {"stale"},
    }
    failures = {"blocked", "stale"} if kind == "plan" else {"blocked", "cancelled"}
    if (
        before == after
        or (before, after) in edges[kind]
        or (before not in terminal[kind] and after in failures)
    ):
        return after
    raise ValueError(f"Forbidden {kind} transition: {before} -> {after}")


def required_evidence(evidence, packages):
    checks = [c for p in packages for t in p.tasks for c in t.checks]
    actual = evidence.get("checks", [])
    if not checks or len(actual) != len(checks) or evidence.get("provenance") != POLICY:
        raise ValueError("Required trusted check evidence is incomplete")
    for check, result in zip(checks, actual, strict=True):
        if (
            check.command != TRUSTED_COMMAND
            or result.get("argv") != check.command
            or result.get("policy") != POLICY
            or result.get("exit_code") != 0
            or result.get("expected") != check.expected
        ):
            raise ValueError("Required trusted check did not pass")
    artifacts = evidence.get("artifacts", {})
    inventory = evidence.get("inventory", {})
    for path in {a for p in packages for a in p.artifacts}:
        digest = artifacts.get(path)
        if not digest or len(digest) != 64 or inventory.get(path) != digest:
            raise ValueError("Required artifact evidence is missing or inconsistent")
    if evidence.get("decisions") or any(s.status == "unresolved" for p in packages for s in p.choices):
        raise ValueError("Unresolved blocking decisions require plan revision")


def make_review(phase, runs, document):
    packages = next(p.packages for p in document.phases if p.id == phase.phase_id)
    records = sorted(
        (
            r
            for r in runs
            if r.plan == phase.plan
            and r.phase_attempt == phase.attempt
            and r.package_id.split("-W")[0] == phase.phase_id
        ),
        key=lambda r: r.package_id,
    )
    if (
        phase.stale
        or phase.integration_intent
        or not phase.staging_commit
        or {r.package_id for r in records} != {p.id for p in packages}
        or len(records) != len(packages)
        or any(
            r.status != "integrated" or not r.integrated_commit or r.stale or r.cancel_requested
            for r in records
        )
    ):
        raise ValueError("Phase packages are incomplete, stale, or uncertain")
    for run in records:
        if any(key in run.evidence for key in ("context_hash", "packet_hash", "context_review_hash")):
            for key in ("context_hash", "packet_hash", "context_review_hash"):
                if not getattr(run, key) or run.evidence.get(key) != getattr(run, key):
                    raise ValueError("Trusted evidence differs from its run context identity")
        required_evidence(run.evidence, [next(p for p in packages if p.id == run.package_id)])
    required_evidence(phase.evidence, packages)
    attempts = sorted(r.id for r in records)
    if phase.evidence.get("package_attempt_ids") != attempts:
        raise ValueError("Aggregate evidence refers to different package attempts")
    payload = {
        "plan": phase.plan.model_dump(),
        "phase_id": phase.phase_id,
        "phase_execution_id": phase.id,
        "attempt": phase.attempt,
        "base_commit": phase.base_commit,
        "staging_commit": phase.staging_commit,
        "package_attempt_ids": attempts,
        "evidence": phase.evidence,
        "packages": [
            {
                "id": r.id,
                "package_id": r.package_id,
                "integrated_commit": r.integrated_commit,
                "evidence": r.evidence,
            }
            for r in records
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return PhaseReview(evidence_hash=hashlib.sha256(encoded.encode()).hexdigest(), payload_json=encoded)


class PhaseReviews:
    def __init__(self, executor):
        self.executor = executor

    def publish(self, phase, document):
        for run in self.executor.phase_runs(phase):
            self.executor.check_context(run)
        review = make_review(phase, self.executor.runs.list(phase.session_id), document)
        self.executor.runs.save_review(review)

        def ready(current):
            if (
                current.attempt != phase.attempt
                or current.staging_commit != phase.staging_commit
                or current.stale
                or current.integration_intent
            ):
                raise ValueError("Phase changed while publishing review")
            current.status = transition("phase", current.status, "awaiting_phase_review")
            current.review_hash = review.evidence_hash

        return self.executor.runs.patch_phase(phase, ready)

    async def validate_tree(self, phase):
        ex = self.executor
        project = await ex.worktrees.owned_project(phase.session_id)
        stage = (await ex.worktrees.git(project, "rev-parse", phase.branch)).strip()
        if stage != phase.staging_commit:
            raise ValueError("Reviewed staging ref moved")
        snapshot = phase.evidence.get("snapshot_commit")
        staged_tree = await ex.verifier.tree(project, stage)
        if staged_tree != await ex.verifier.tree(project, snapshot):
            raise ValueError("Aggregate evidence does not describe the reviewed staging tree")
        hashes = {}
        for path, (_, oid) in staged_tree.items():
            data = await ex.worktrees.git_bytes(project, "cat-file", "blob", oid)
            hashes[path] = hashlib.sha256(data).hexdigest()
        if hashes != phase.evidence.get("inventory"):
            raise ValueError("Reviewed artifact inventory differs from staging bytes")
        return project

    async def decide(self, session_id, identity, phase_id, evidence_hash, decision, notes=""):
        ex = self.executor
        document = ex.guard(ex.sessions.get(session_id), identity)
        phase = ex.runs.phase(session_id, identity.content_hash, phase_id)
        if (
            phase.plan != identity
            or phase.review_hash != evidence_hash
            or phase.stale
            or decision not in {"accept", "reject"}
        ):
            raise ValueError("Review identity is stale or decision is invalid")
        for run in ex.phase_runs(phase):
            ex.check_context(run)
        review = make_review(phase, ex.runs.list(session_id), document)
        if review.evidence_hash != evidence_hash or ex.runs.review(evidence_hash) != review:
            raise ValueError("Review evidence changed; reload the current immutable review")
        if phase.status == "accepted" and phase.decision == decision == "accept":
            project = await ex.worktrees.owned_project(session_id)
            if (
                await ex.worktrees.git(project, "rev-parse", "refs/heads/accepted")
            ).strip() != phase.staging_commit:
                raise ValueError("Accepted ref moved; reconcile before continuing")
            return phase
        if phase.status != "awaiting_phase_review" or phase.promotion_intent:
            raise ValueError("Phase is no longer awaiting this review")
        if decision == "reject":

            def reject(current):
                if current.status != "awaiting_phase_review" or current.promotion_intent:
                    raise ValueError("Review was already decided")
                current.status = transition("phase", current.status, "blocked")
                current.decision, current.review_notes = "reject", notes
                current.error = "Phase rejected; explicit repair is required"

            return ex.runs.patch_phase(phase, reject)

        project = await self.validate_tree(phase)
        if await ex.worktrees.changed_paths(project):
            raise ValueError("Owned project is dirty; preserve changes before promotion")
        # Keep the management checkout at its existing tree. Promotion only advances the accepted ref.
        head = (await ex.worktrees.git(project, "rev-parse", "HEAD")).strip()
        await ex.worktrees.git(project, "update-ref", "--no-deref", "HEAD", head, head)

        def reserve(current):
            if (
                current.status != "awaiting_phase_review"
                or current.review_hash != evidence_hash
                or current.promotion_intent
                or current.stale
                or current.attempt != phase.attempt
            ):
                raise ValueError("Review changed before promotion")
            current.promotion_intent = evidence_hash
            current.review_notes = notes

        ex.runs.patch_phase(phase, reserve)
        try:
            await ex.worktrees.git(
                project, "update-ref", "refs/heads/accepted", phase.staging_commit, phase.base_commit
            )
            ex.guard(ex.sessions.get(session_id), identity)

            def accept(current):
                if current.promotion_intent != evidence_hash or current.stale:
                    raise ValueError("Phase changed during promotion; reconcile the outcome")
                current.status = transition("phase", current.status, "accepted")
                current.promotion_intent = None
                current.decision, current.error = "accept", None

            return ex.runs.patch_phase(phase, accept)
        except BaseException:
            ex.block_phase(phase, "Promotion outcome requires reconciliation; no automatic replay")
            raise
