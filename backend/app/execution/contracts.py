import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..codex.client import Approval
from ..planning.contracts import PlanApproval


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    plan: PlanApproval
    package_id: str
    status: Literal["queued", "running", "verifying", "integrated", "blocked", "cancelled"] = "queued"
    owned_paths: list[str] = Field(default_factory=list, max_length=20)
    interfaces: list[str] = Field(default_factory=list, max_length=20)
    integrated_commit: str | None = None
    evidence: dict = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    deadline: float = Field(default_factory=lambda: time.time() + 300)
    project: str | None = None
    worktree: str | None = None
    base_commit: str | None = None
    profile: str = "configured-local-profile"
    account_fingerprint: str | None = None
    model: str | None = None
    selected_model: str | None = None
    generation: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    dispatch_intent: str | None = None
    cancel_requested: bool = False
    stale: bool = False
    approvals: list[Approval] = Field(default_factory=list, max_length=32)
    logs: list[str] = Field(default_factory=list, max_length=64)
    changed_paths: list[str] = Field(default_factory=list, max_length=1024)
    turn_status: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict, max_length=8)
    error: str | None = None

    def public(self):
        return self.model_dump(mode="json", exclude={"account_fingerprint", "profile"})


class PhaseExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    plan: PlanApproval
    phase_id: str
    status: Literal["running", "verifying", "awaiting_phase_review", "blocked", "cancelled"] = "running"
    base_commit: str | None = None
    staging_commit: str | None = None
    staging_worktree: str | None = None
    integration_intent: str | None = None
    evidence: dict = Field(default_factory=dict)
    error: str | None = None

    @property
    def branch(self):
        return f"refs/heads/intent/{self.plan.content_hash}/{self.phase_id}"
