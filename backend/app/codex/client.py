import hashlib
import time
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .protocol import QUALIFIED_VERSION, CodexError

THREAD_POLICY = {
    "sandbox": "workspace-write",
    "approvalPolicy": "on-request",
    "approvalsReviewer": "user",
    "config": {
        "features.multi_agent": False,
        "features.collab": False,
        "web_search": "disabled",
        "sandbox_workspace_write.network_access": False,
        "sandbox_workspace_write.exclude_slash_tmp": True,
        "sandbox_workspace_write.exclude_tmpdir_env_var": True,
        "shell_environment_policy.inherit": "none",
    },
}


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid4()))
    server_id: int | str
    generation: str
    thread_id: str
    turn_id: str
    item_id: str
    method: str
    expires_at: float
    command: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=1000)
    status: str = "pending"


class Client:
    def __init__(self, transport, approval_timeout=120):
        self.transport = transport
        self.approval_timeout = approval_timeout
        self.pending: dict[str, Approval] = {}
        self.seen: set[int | str] = set()
        self.account_fingerprint = None
        self.selected_model = None

    async def qualify(self, cwd: str, model: str | None = None, expected_account: str | None = None):
        await self.transport.initialize()
        account = (await self.transport.request("account/read", {"refreshToken": False})).get("account")
        if not isinstance(account, dict) or account.get("type") != "chatgpt" or not account.get("email"):
            raise CodexError("Execution requires an identifiable Codex-managed ChatGPT login")
        fingerprint = hashlib.sha256(account["email"].strip().casefold().encode()).hexdigest()
        if expected_account and fingerprint != expected_account:
            raise CodexError("The Codex account differs from the saved run")
        self.account_fingerprint = fingerprint
        config = (await self.transport.request("config/read", {"cwd": cwd, "includeLayers": False}))["config"]
        if config.get("model_provider") not in {None, "openai"} or config.get("model_providers"):
            raise CodexError("Custom billing/provider settings are unsupported for this executor")
        for key in ("mcp_servers", "plugins", "hooks", "notify", "apps", "browser_use", "computer_use"):
            if config.get(key):
                raise CodexError("Inherited tools or hooks require a separately qualified Codex profile")
        servers = await self.transport.request("mcpServerStatus/list", {"limit": 100})
        if servers.get("data") or servers.get("nextCursor"):
            raise CodexError("Inherited MCP servers are unsupported for this executor")
        skills = await self.transport.request("skills/list", {"cwds": [cwd], "forceReload": False})
        if any(
            entry.get("errors") or any(s.get("enabled", True) for s in entry.get("skills", []))
            for entry in skills.get("data", [])
        ):
            raise CodexError("Inherited skills require a separately qualified Codex profile")
        available, defaults, cursor = set(), set(), None
        for _ in range(5):
            page = await self.transport.request(
                "model/list", {"limit": 100, **({"cursor": cursor} if cursor else {})}
            )
            available.update(x["model"] for x in page.get("data", []))
            defaults.update(x["model"] for x in page.get("data", []) if x.get("isDefault"))
            cursor = page.get("nextCursor")
            if not cursor:
                break
        if cursor:
            raise CodexError("Codex model inventory exceeds the supported bound")
        implicit_default = next(iter(defaults)) if len(defaults) == 1 else None
        self.selected_model = model or config.get("model") or implicit_default
        if not self.selected_model or self.selected_model not in available:
            raise CodexError("The selected or configured model is unavailable; choose an available model")
        limits = await self.transport.request("account/rateLimits/read", {})
        self.check_limits(limits)
        return {"type": "chatgpt", "model": self.selected_model}

    @staticmethod
    def check_limits(limits):
        snapshots = limits.get("rateLimitsByLimitId") or {"codex": limits.get("rateLimits", {})}
        if limits.get("ordinaryUsageAllowed") is False or any(
            window and window.get("usedPercent", 0) >= 100
            for snapshot in snapshots.values()
            for window in [snapshot.get("primary"), snapshot.get("secondary")]
        ):
            raise CodexError("Codex account usage limit reached; further dispatch is blocked")

    async def start_thread(self, cwd: str, model: str | None = None):
        if not self.account_fingerprint:
            raise CodexError("Qualify Codex account and policy before dispatch")
        result = await self.transport.request(
            "thread/start",
            {
                **THREAD_POLICY,
                "cwd": cwd,
                **({"model": model} if model else {}),
            },
        )
        thread = result["thread"]
        if thread.get("cliVersion") != QUALIFIED_VERSION or not thread.get("id"):
            raise CodexError("Codex CLI version differs from the qualified protocol")
        return thread["id"]

    async def start_turn(self, thread_id: str, packet: str, cwd: str):
        result = await self.transport.request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": packet}],
                "cwd": cwd,
                "approvalPolicy": "on-request",
                "approvalsReviewer": "user",
                "sandboxPolicy": {
                    "type": "workspaceWrite",
                    "writableRoots": [cwd],
                    "networkAccess": False,
                    "excludeSlashTmp": True,
                    "excludeTmpdirEnvVar": True,
                },
            },
        )
        return result["turn"]["id"]

    async def next_event(self, thread_id: str, turn_id: str, timeout=None):
        deadline = time.monotonic() + (timeout or self.transport.timeout)
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise CodexError("Codex event deadline reached")
            event = await self.transport.next_message(left)
            params = event.get("params", {})
            if event["method"] == "account/rateLimits/updated":
                self.check_limits(params)
                continue
            matches = params.get("threadId") == thread_id and (
                params.get("turnId") == turn_id or params.get("turn", {}).get("id") == turn_id
            )
            if matches:
                if event["method"] == "error":
                    raise CodexError("Codex turn failed; inspect the preserved work")
                return event
            if "id" in event:
                raise CodexError("Codex approval request belongs to a different run")

    def approval(self, event: dict, thread_id: str, turn_id: str) -> Approval:
        params = event.get("params", {})
        if (
            event.get("method")
            not in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}
            or "id" not in event
            or event["id"] in self.seen
            or params.get("threadId") != thread_id
            or params.get("turnId") != turn_id
            or not params.get("itemId")
            or len(self.pending) >= 16
        ):
            raise CodexError("Unsupported, duplicate, or stale Codex permission request; no access granted")
        request = Approval(
            server_id=event["id"],
            generation=self.transport.generation,
            thread_id=thread_id,
            turn_id=turn_id,
            item_id=params["itemId"],
            method=event["method"],
            expires_at=time.time() + self.approval_timeout,
            command=str(params.get("command") or "")[:2000],
            reason=str(params.get("reason") or "")[:1000],
        )
        self.seen.add(event["id"])
        self.pending[request.id] = request
        return request

    async def decide(self, approval: Approval, decision: str, *, generation: str):
        current = self.pending.get(approval.id)
        if (
            current != approval
            or approval.status != "pending"
            or decision not in {"accept", "decline", "cancel"}
            or generation != self.transport.generation
            or approval.generation != generation
            or approval.expires_at <= time.time()
        ):
            raise CodexError("Permission request expired, changed, or was already answered")
        # Consume before the external write: an uncertain response cannot be replayed.
        approval.status = "responding"
        self.pending.pop(approval.id)
        await self.transport.send({"id": approval.server_id, "result": {"decision": decision}})
        approval.status = decision

    async def reconcile(self, thread_id: str, turn_id: str):
        result = await self.transport.request("thread/read", {"threadId": thread_id, "includeTurns": True})
        thread = result.get("thread", {})
        if thread.get("id") != thread_id:
            raise CodexError("Saved Codex thread does not match the requested run")
        return next(
            (turn["status"] for turn in thread.get("turns", []) if turn.get("id") == turn_id), "unknown"
        )

    async def resume(self, thread_id: str, cwd: str, model: str | None = None):
        await self.transport.request(
            "thread/resume",
            {
                **THREAD_POLICY,
                "threadId": thread_id,
                "cwd": cwd,
                "excludeTurns": True,
                **({"model": model} if model else {}),
            },
        )

    async def interrupt(self, thread_id: str, turn_id: str):
        await self.transport.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})

    async def close(self):
        await self.transport.close()
