import sys
from pathlib import Path

import pytest

from backend.app.codex.client import Client
from backend.app.codex.protocol import CodexError
from backend.app.codex.transport import Transport

FAKE = Path(__file__).parent / "fixtures/codex/fake_server.py"


async def client(scenario="success", **kwargs):
    transport = Transport([sys.executable, "-u", str(FAKE), scenario])
    await transport.start()
    return Client(transport, **kwargs)


@pytest.mark.parametrize("model", [None, "synthetic-selected"])
async def test_preserves_default_or_explicit_model_and_filters_foreign_events(tmp_path, model):
    connection = await client()
    try:
        account = await connection.qualify(str(tmp_path), model)
        assert account["type"] == "chatgpt" and "email" not in account
        assert connection.selected_model == (model or "synthetic-default")
        thread = await connection.start_thread(str(tmp_path), model)
        turn = await connection.start_turn(thread, "Synthetic task packet", str(tmp_path))
        assert (await connection.next_event(thread, turn))["method"] == "item/agentMessage/delta"
        result = await connection.next_event(thread, turn)
        assert result["params"]["turn"]["status"] == "completed"
    finally:
        await connection.close()


@pytest.mark.parametrize("scenario", ["no_account", "api_key", "limit", "unsafe_config"])
async def test_ineligible_accounts_limits_and_inherited_tools_block(tmp_path, scenario):
    connection = await client(scenario)
    try:
        with pytest.raises(CodexError):
            await connection.qualify(str(tmp_path))
    finally:
        await connection.close()


async def test_unavailable_model_is_not_substituted(tmp_path):
    connection = await client()
    try:
        with pytest.raises(CodexError, match="model"):
            await connection.qualify(str(tmp_path), "missing")
    finally:
        await connection.close()


@pytest.mark.parametrize("decision,status", [("accept", "completed"), ("decline", "interrupted")])
async def test_approval_identity_deadlines_and_replay(tmp_path, decision, status):
    connection = await client("approval")
    try:
        await connection.qualify(str(tmp_path))
        thread = await connection.start_thread(str(tmp_path))
        turn = await connection.start_turn(thread, "Synthetic", str(tmp_path))
        event = await connection.next_event(thread, turn)
        approval = connection.approval(event, thread, turn)
        with pytest.raises(CodexError):
            await connection.decide(approval, decision, generation="stale")
        await connection.decide(approval, decision, generation=connection.transport.generation)
        with pytest.raises(CodexError):
            await connection.decide(approval, decision, generation=connection.transport.generation)
        assert (await connection.next_event(thread, turn))["params"]["turn"]["status"] == status
    finally:
        await connection.close()


async def test_unknown_approval_never_grants_access(tmp_path):
    connection = await client("unknown_approval")
    try:
        await connection.qualify(str(tmp_path))
        thread = await connection.start_thread(str(tmp_path))
        turn = await connection.start_turn(thread, "Synthetic", str(tmp_path))
        with pytest.raises(CodexError):
            connection.approval(await connection.next_event(thread, turn), thread, turn)
    finally:
        await connection.close()


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("success", "completed"),
        ("interrupted", "interrupted"),
        ("missing_turn", "unknown"),
        ("running", "inProgress"),
    ],
)
async def test_reconciliation_reads_existing_turn_without_restarting(tmp_path, scenario, expected):
    connection = await client(scenario)
    try:
        await connection.qualify(str(tmp_path))
        assert await connection.reconcile("synthetic-thread", "synthetic-turn") == expected
    finally:
        await connection.close()
