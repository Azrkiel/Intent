import time
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, StringConstraints, field_validator

from ..planning.contracts import PlanningModel

Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class DiscussionTarget(PlanningModel):
    kind: Literal["plan", "intent"]
    requirements_revision: int = Field(ge=0)
    plan_id: str | None = Field(default=None, max_length=2000)
    plan_revision: int | None = Field(default=None, ge=1)
    plan_hash: Hash | None = None
    node_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    node_hash: Hash


class DiscussionRequest(PlanningModel):
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    target: DiscussionTarget
    mode: Literal["question", "direction"]
    text: str = Field(min_length=1, max_length=6000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a question or direction first")
        return value


class DiscussionReply(PlanningModel):
    text: str = Field(min_length=1, max_length=6000)
    citations: list[str] = Field(default_factory=list, max_length=40)
    follow_up: str | None = Field(default=None, max_length=2000)
    proposed_direction: str | None = Field(default=None, max_length=2000)


class DiscussionMessage(PlanningModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    mode: Literal["question", "direction"]
    text: str
    status: Literal["pending", "complete", "failed", "uncertain"] = "pending"
    reply: DiscussionReply | None = None
    error: str | None = None
    turn_number: int | None = None
    created_at: float = Field(default_factory=time.time)
