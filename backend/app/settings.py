from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .clarity.contracts import ReaderVariation, Thresholds


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    mode: Literal["demo", "live"] = Field(default="demo", validation_alias="PROMPT_CALLER_MODE")
    nebius_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NEBIUS_API_KEY", "TOKEN_FACTORY_API_KEY")
    )
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nano_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    super_model: str = "nvidia/nemotron-3-super-120b-a12b"
    ultra_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    send_thinking_controls: bool = False
    # Opt-in, Nano clarity passes only: faster, but the live rubric judge then failed W1 on "I".
    nano_thinking_off: bool = False
    reasoning_budget: int = Field(default=2048, ge=256, le=8192)
    session_budget_usd: float = Field(default=2, gt=0, le=100)
    database_path: str = ".data/prompt-caller.sqlite3"
    frontend_port: int = Field(default=3000, ge=1, le=65535)
    build_root: str = ".data/builds"
    claude_command: str = "claude"
    claude_max_budget_usd: float = Field(default=2, gt=0, le=100)
    build_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    allow_claude_build: bool = False
    planning_max_attempts: int = Field(default=2, ge=1, le=2)
    planning_max_passes: int = Field(default=9, ge=1, le=9)
    clarity_version: int | None = Field(default=None, ge=1, le=2)
    clarity_reader_variation: ReaderVariation = "perspective"
    clarity_alpha_pass: float = Field(default=0.80, ge=0, le=1)
    clarity_alpha_floor: float = Field(default=0.667, ge=0, le=1)
    canary_critical_recall: float = Field(default=1.0, ge=0, le=1)
    canary_overall_recall: float = Field(default=0.80, ge=0, le=1)
    decision_stop_threshold: float = Field(default=1.5, ge=0, le=9)
    decision_repeat_penalty: float = Field(default=0.5, ge=0, le=9)

    def resolved_clarity_version(self) -> int:
        return self.clarity_version or (2 if self.mode == "live" else 1)

    def thresholds(self) -> Thresholds:
        return Thresholds(
            alpha_pass=self.clarity_alpha_pass, alpha_floor=self.clarity_alpha_floor,
            canary_critical_recall=self.canary_critical_recall,
            canary_overall_recall=self.canary_overall_recall,
            decision_stop=self.decision_stop_threshold, repeat_penalty=self.decision_repeat_penalty,
        )
    allow_codex_execution: bool = False
    codex_command: str = "codex"
    codex_home: str | None = None
    codex_project_root: str = ".data/projects"
    codex_worktree_root: str = ".data/worktrees"
    codex_max_workers: int = Field(default=1, ge=1, le=2)
    codex_global_max_workers: int = Field(default=2, ge=1, le=2)
    codex_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    codex_approval_timeout_seconds: int = Field(default=120, ge=1, le=300)
