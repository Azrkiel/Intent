"""Install offline defaults during collection, before module-level apps are created."""

import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.app.settings import Settings

# Tests may supply explicit _env_file paths and fake environment values themselves.
# The developer's real .env and exported runtime settings are never test defaults.
Settings.model_config["env_file"] = None
for name, field in Settings.model_fields.items():
    aliases = [name.upper()]
    if isinstance(field.validation_alias, str):
        aliases.append(field.validation_alias)
    elif field.validation_alias is not None:
        aliases.extend(field.validation_alias.choices)
    for alias in aliases:
        os.environ.pop(alias, None)
os.environ["DATABASE_PATH"] = str(Path.cwd() / ".data" / "pytest" / str(uuid4()) / "sessions.sqlite3")


@pytest.fixture(autouse=True)
def require_mocked_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline tests must mock network transports")

    async def blocked_async(*args, **kwargs):
        raise AssertionError("Offline tests must mock network transports")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked_async)
