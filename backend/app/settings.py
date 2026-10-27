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
    build_root: str = ".data/builds"
    claude_command: str = "claude"
    claude_max_budget_usd: float = Field(default=2, gt=0, le=100)
    build_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    allow_claude_build: bool = False
