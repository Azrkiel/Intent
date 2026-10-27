import asyncio
import sys
from pathlib import Path

import pytest

from backend.app.codex.protocol import CodexError
from backend.app.codex.transport import Transport

FAKE = Path(__file__).parent / "fixtures/codex/fake_server.py"


async def connect(**kwargs):
    transport = Transport([sys.executable, "-u", str(FAKE)], **kwargs)
    await transport.start()
    await transport.initialize()
    return transport


async def test_split_frames_notifications_and_out_of_order_replies():
    transport = await connect()
    try:
        assert await transport.request("test/echo", {"value": 1}) == {"value": 1}
        assert (await transport.next_message())["method"] == "test/progress"
        results = await asyncio.gather(
            transport.request("test/reorder", {"value": 2}), transport.request("test/reorder", {"value": 3})
        )
        assert results == [{"value": 2}, {"value": 3}]
        await transport.initialize()  # Local idempotency; no second handshake on the wire.
    finally:
        await transport.close()
    assert transport.process.returncode is not None


@pytest.mark.parametrize("method", ["test/malformed", "test/oversized", "test/exit", "test/hang"])
async def test_failures_are_bounded_and_fail_pending_requests(method):
    transport = await connect(max_frame=2048, timeout=0.5)
    try:
        with pytest.raises(CodexError):
            await transport.request(method, {})
    finally:
        await transport.close()


async def test_stderr_is_drained_and_credentials_are_not_inherited(monkeypatch):
    for name in ("NEBIUS_API_KEY", "OPENAI_API_KEY", "ACCESS_TOKEN", "INTENT_SECRET"):
        monkeypatch.setenv(name, "synthetic-secret")
    transport = await connect()
    try:
        await transport.request("test/stderr", {})
        assert await transport.request("test/environment", {}) == {"secret_inherited": False}
        assert transport.stderr_bytes <= 65536
    finally:
        await transport.close()


async def test_cancellation_releases_pending_request():
    transport = await connect()
    try:
        task = asyncio.create_task(transport.request("test/hang", {}))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not transport.pending
    finally:
        await transport.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows descendant cleanup")
@pytest.mark.parametrize("parent_exits", [False, True])
async def test_close_terminates_owned_child_process(tmp_path, parent_exits):
    import ctypes
    from ctypes import wintypes

    transport = await connect()
    path = tmp_path / "child.pid"
    if parent_exits:
        with pytest.raises(CodexError):
            await transport.request("test/orphan", {"path": str(path)})
    else:
        await transport.request("test/child", {"path": str(path)})
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = kernel.OpenProcess(0x100001, False, int(path.read_text()))
    assert handle
    try:
        await transport.close()
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        assert kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess(handle, 0)
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
