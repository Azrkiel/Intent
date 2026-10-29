from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    allow_codex_execution: bool = False
    codex_command: str = "codex"
    codex_home: str | None = None
    codex_project_root: str = ".data/projects"
    codex_worktree_root: str = ".data/worktrees"
    codex_max_workers: int = Field(default=1, ge=1, le=2)
    codex_global_max_workers: int = Field(default=2, ge=1, le=2)
    codex_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    codex_approval_timeout_seconds: int = Field(default=120, ge=1, le=300)
