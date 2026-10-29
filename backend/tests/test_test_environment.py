import httpx
import pytest

from backend.app.settings import Settings


def test_offline_defaults_ignore_a_local_live_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "PROMPT_CALLER_MODE=live\nNEBIUS_API_KEY=offline-test-canary\n"
        "ALLOW_CODEX_EXECUTION=true\nDATABASE_PATH=production.sqlite3\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config = Settings()
    configured = bool(config.nebius_api_key and config.nebius_api_key.get_secret_value())
    assert config.mode == "demo"
    assert not configured
    assert not config.allow_codex_execution
    assert config.database_path != "production.sqlite3"


async def test_unmocked_network_is_blocked_before_connecting():
    async with httpx.AsyncClient() as client:
        with pytest.raises(AssertionError, match="Offline tests must mock network"):
            await client.get("https://offline-test.invalid")
    with httpx.Client() as client:
        with pytest.raises(AssertionError, match="Offline tests must mock network"):
            client.get("https://offline-test.invalid")


async def test_mocked_provider_hosts_remain_available():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"synthetic": True}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await client.get("https://provider-test.invalid")
    assert result.json() == {"synthetic": True}
