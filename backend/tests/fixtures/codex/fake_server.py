"""Synthetic JSONL app-server. Never contacts a provider or reads authentication."""

import json
import os
import subprocess
import sys
from pathlib import Path

scenario = sys.argv[1] if len(sys.argv) > 1 else "success"
thread_id, turn_id = "synthetic-thread", "synthetic-turn"
initialized = False
notifications_enabled = False
pending = None


def send(value):
    line = (json.dumps(value) + "\n").encode()
    split = len(line) // 2
    sys.stdout.buffer.write(line[:split])
    sys.stdout.buffer.flush()
    sys.stdout.buffer.write(line[split:])
    sys.stdout.buffer.flush()


def event(method, params):
    send({"method": method, "params": params})


def complete(status="completed"):
    usage = {
        "inputTokens": 12,
        "outputTokens": 5,
        "totalTokens": 17,
        "cachedInputTokens": 0,
        "reasoningOutputTokens": 0,
        "cacheWriteInputTokens": 0,
    }
    event(
        "thread/tokenUsage/updated",
        {"threadId": thread_id, "turnId": turn_id, "tokenUsage": {"total": usage, "last": usage}},
    )
    event("turn/completed", {"threadId": thread_id, "turn": {"id": turn_id, "status": status, "items": []}})


for line in sys.stdin:
    message = json.loads(line)
    if "method" not in message:
        if scenario == "approval":
            complete("completed" if message.get("result", {}).get("decision") == "accept" else "interrupted")
        continue
    method, params = message["method"], message.get("params", {})
    id = message.get("id")
    if method == "initialize":
        assert not initialized
        initialized = True
        result = {"userAgent": "synthetic/0.164.0"}
    elif method == "initialized":
        notifications_enabled = True
        continue
    else:
        assert initialized and notifications_enabled
        if method == "test/echo":
            event("test/progress", {"value": "synthetic"})
            result = params
        elif method == "test/reorder":
            if pending is None:
                pending = message
                continue
            send({"id": id, "result": params})
            send({"id": pending["id"], "result": pending["params"]})
            pending = None
            continue
        elif method == "test/hang":
            continue
        elif method in {"test/child", "test/orphan"}:
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
            Path(params["path"]).write_text(str(child.pid))
            if method == "test/orphan":
                sys.exit(3)
            result = {"pid": child.pid}
        elif method == "test/malformed":
            print("invalid json", flush=True)
            continue
        elif method == "test/oversized":
            print("x" * 10000, flush=True)
            continue
        elif method == "test/exit":
            sys.exit(4)
        elif method == "test/stderr":
            sys.stderr.write("synthetic diagnostic\n" * 10000)
            sys.stderr.flush()
            result = {}
        elif method == "test/environment":
            result = {
                "secret_inherited": any(
                    k in os.environ
                    for k in ["NEBIUS_API_KEY", "OPENAI_API_KEY", "ACCESS_TOKEN", "INTENT_SECRET"]
                )
            }
        elif method == "account/read":
            account = (
                None
                if scenario == "no_account"
                else {"type": "apiKey"}
                if scenario == "api_key"
                else {"type": "chatgpt", "email": "synthetic@example.invalid", "planType": "unknown"}
            )
            result = {"account": account, "requiresOpenaiAuth": True}
        elif method == "account/rateLimits/read":
            result = {
                "rateLimits": {"primary": {"usedPercent": 100 if scenario == "limit" else 10}},
                "ordinaryUsageAllowed": scenario != "limit",
            }
        elif method == "config/read":
            result = {
                "config": {
                    "model": None if scenario == "implicit_model" else "synthetic-default",
                    "model_provider": "openai",
                    "mcp_servers": {"external": {}} if scenario == "unsafe_config" else {},
                },
                "origins": {},
            }
        elif method == "model/list":
            result = {
                "data": [
                    {"id": "synthetic-default", "model": "synthetic-default", "isDefault": True},
                    {"id": "synthetic-selected", "model": "synthetic-selected"},
                ],
                "nextCursor": None,
            }
        elif method == "mcpServerStatus/list":
            result = {"data": [], "nextCursor": None}
        elif method == "skills/list":
            result = {"data": [{"cwd": str(Path.cwd()), "skills": [], "errors": []}]}
        elif method == "thread/start":
            assert scenario != "reconcile_only"
            assert params["sandbox"] == "workspace-write"
            assert params["approvalPolicy"] == "on-request"
            assert params["approvalsReviewer"] == "user"
            assert params["config"]["features.multi_agent"] is False
            thread = {
                "id": thread_id,
                "cwd": params["cwd"],
                "model": params.get("model", "synthetic-default"),
                "cliVersion": "0.164.0",
                "turns": [],
            }
            result = {"thread": thread}
        elif method in {"thread/read", "thread/resume"}:
            status = (
                "inProgress"
                if scenario == "running"
                else "interrupted"
                if scenario == "interrupted"
                else "completed"
            )
            result = {
                "thread": {
                    "id": thread_id,
                    "turns": []
                    if scenario == "missing_turn"
                    else [{"id": turn_id, "status": status, "items": []}],
                }
            }
        elif method == "turn/start":
            assert scenario != "reconcile_only"
            if scenario == "lost_start":
                sys.exit(2)
            result = {"turn": {"id": turn_id, "status": "inProgress", "items": []}}
            send({"id": id, "result": result})
            event(
                "item/agentMessage/delta",
                {
                    "threadId": "other-thread",
                    "turnId": turn_id,
                    "itemId": "wrong",
                    "delta": "Must be ignored",
                },
            )
            if scenario in {"approval", "unknown_approval"}:
                send(
                    {
                        "id": "approval-1",
                        "method": "item/commandExecution/requestApproval"
                        if scenario == "approval"
                        else "unknown/requestApproval",
                        "params": {
                            "threadId": thread_id,
                            "turnId": turn_id,
                            "itemId": "command-1",
                            "startedAtMs": 1,
                            "command": "synthetic check",
                            "cwd": str(Path.cwd()),
                        },
                    }
                )
            elif scenario == "hang":
                continue
            else:
                if scenario == "outside":
                    Path("outside.txt").write_text("Synthetic out-of-scope change")
                if scenario in {"artifact", "scoped_artifact"}:
                    directory = "contracts"
                    if (
                        scenario == "scoped_artifact"
                        and "P1-W2"
                        in params["input"][0]["text"]
                        .split("Assigned task packet (quoted product data):", 1)[1]
                        .lstrip()
                        .splitlines()[0]
                    ):
                        directory = "api"
                    if (
                        scenario == "scoped_artifact"
                        and "P2-W1"
                        in (
                            params["input"][0]["text"]
                            .split("Assigned task packet (quoted product data):", 1)[1]
                            .lstrip()
                            .splitlines()[0]
                        )
                    ):
                        directory = "ui"
                    Path(directory).mkdir(exist_ok=True)
                    (Path(directory) / "result.txt").write_text("Synthetic artifact")
                event(
                    "item/agentMessage/delta",
                    {
                        "threadId": thread_id,
                        "turnId": turn_id,
                        "itemId": "summary",
                        "delta": "Synthetic worker report",
                    },
                )
                complete(
                    "failed"
                    if scenario == "failed"
                    else "interrupted"
                    if scenario == "interrupted"
                    else "completed"
                )
            continue
        elif method == "turn/interrupt":
            send({"id": id, "result": {}})
            complete("interrupted")
            continue
        else:
            send({"id": id, "error": {"code": -32601, "message": "Synthetic unknown method"}})
            continue
    send({"id": id, "result": result})
