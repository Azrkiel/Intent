import asyncio
import json
import os
import re
import signal
from uuid import uuid4

from .protocol import CodexError, decode


def child_environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "CODEX_HOME",
        "LANG",
        "LC_ALL",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class Transport:
    def __init__(
        self, argv: list[str], *, cwd=None, timeout=15.0, max_frame=1_000_000, queue_size=256, home=None
    ):
        self.argv, self.cwd, self.timeout, self.max_frame = argv, cwd, timeout, max_frame
        self.generation = str(uuid4())
        self.process = None
        self.pending: dict[int, asyncio.Future] = {}
        self.messages = asyncio.Queue(maxsize=queue_size)
        self.failure = None
        self.failed = asyncio.Event()
        self.writer = asyncio.Lock()
        self.handshake = asyncio.Lock()
        self.initialized = False
        self.server_version = None
        self.counter = 0
        self.tasks = []
        self.stderr_bytes = 0
        self.job = None
        self.home = home

    async def start(self):
        if self.process:
            raise CodexError("This transport has already started")
        try:
            env = child_environment()
            if self.home:
                env["CODEX_HOME"] = self.home
            self.process = await asyncio.create_subprocess_exec(
                *self.argv,
                cwd=self.cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=self.max_frame,
                start_new_session=os.name != "nt",
            )
            if os.name == "nt":
                from .process import WindowsJob

                self.job = WindowsJob(self.process.pid)
        except OSError as error:
            if self.process and self.process.returncode is None:
                self.process.kill()
                await self.process.wait()
            raise CodexError("Cannot start the configured Codex command") from error
        self.tasks = [asyncio.create_task(self.read()), asyncio.create_task(self.drain_stderr())]

    def fail(self, message: str):
        if self.failure is None:
            self.failure = CodexError(message)
            self.failed.set()
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(self.failure)

    async def read(self):
        try:
            while line := await self.process.stdout.readline():
                if len(line) > self.max_frame:
                    raise CodexError("Codex protocol frame exceeds its limit")
                message = decode(line)
                if "method" in message:
                    self.messages.put_nowait(message)
                else:
                    future = self.pending.get(message["id"])
                    if future and not future.done():
                        if "error" in message:
                            future.set_exception(CodexError("Codex rejected a protocol request"))
                        else:
                            future.set_result(message["result"])
            self.fail("Codex connection closed; reconcile the saved run before retrying")
        except asyncio.CancelledError:
            raise
        except (ValueError, CodexError, asyncio.QueueFull):
            self.fail("Codex protocol or event capacity limit reached")
        except Exception:
            self.fail("Codex transport failed")

    async def drain_stderr(self):
        while chunk := await self.process.stderr.read(4096):
            # Drain pressure without retaining credentials or untrusted diagnostic bodies.
            self.stderr_bytes = min(65536, self.stderr_bytes + len(chunk))

    async def send(self, message: dict):
        if self.failure or self.process is None:
            raise self.failure or CodexError("Codex transport has not started")
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > self.max_frame:
            raise CodexError("Outgoing Codex frame exceeds its limit")
        async with self.writer:
            try:
                self.process.stdin.write(data)
                await asyncio.wait_for(self.process.stdin.drain(), self.timeout)
            except (OSError, TimeoutError) as error:
                self.fail("Codex write failed; reconcile the saved run")
                raise self.failure from error

    async def request(self, method: str, params: dict):
        if len(self.pending) >= 64:
            raise CodexError("Too many pending Codex requests")
        self.counter += 1
        id = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[id] = future
        try:
            await self.send({"id": id, "method": method, "params": params})
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError as error:
            raise CodexError("Codex request timed out; its external outcome is uncertain") from error
        finally:
            self.pending.pop(id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Retrieve failures if send failed before awaiting the future.

    async def initialize(self):
        async with self.handshake:
            if not self.initialized:
                result = await self.request(
                    "initialize", {"clientInfo": {"name": "intent", "title": "Intent", "version": "0.1.0"}}
                )
                agent = re.match(r"[^/\s]+/(\S+)", str(result.get("userAgent", "")))
                self.server_version = agent.group(1) if agent else None
                await self.send({"method": "initialized"})
                self.initialized = True

    async def next_message(self, timeout=None):
        if not self.messages.empty():
            return self.messages.get_nowait()
        if self.failure:
            raise self.failure
        get = asyncio.create_task(self.messages.get())
        failed = asyncio.create_task(self.failed.wait())
        try:
            done, _ = await asyncio.wait(
                [get, failed], timeout=timeout or self.timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if get in done:
                return get.result()
            if failed in done:
                raise self.failure
            raise CodexError("Codex event deadline reached")
        finally:
            for task in (get, failed):
                if not task.done():
                    task.cancel()
            await asyncio.gather(get, failed, return_exceptions=True)

    async def close(self):
        self.fail("Codex connection closed")
        if self.job:
            self.job.close()
        if self.process:
            if os.name != "nt":
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if self.process.returncode is None:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            await asyncio.wait_for(self.process.wait(), 5)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
