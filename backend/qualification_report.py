"""Allowlisted qualification metadata; never serialize sessions or provider errors."""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

FAILURES = {
    "missing_credentials",
    "execution_disabled",
    "approved_session_required",
    "profile_unavailable",
    "planning_failed",
    "plan_review_required",
    "manual_audit_required",
    "execution_failed",
    "phase_review_required",
    "context_review_required",
    "cleanup_failed",
    "invalid_configuration",
}
MODELS = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/Nemotron-3-Ultra-550b-a55b",
    "nvidia/Nemotron-3_5-Lightning",
}


def model_label(value):
    if value in MODELS or (isinstance(value, str) and re.fullmatch(r"gpt-\d+(?:\.\d+)?(?:-codex)?", value)):
        return value
    return "custom_model_redacted"


def number(value, integer=False):
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
        return 0
    return int(value) if integer else value


def write_report(output, scope, record):
    usage = []
    for item in record.get("usage", []):
        role = item.get("role", "")
        role = next(
            (
                r
                for r in ("outline", "screen", "phase", "verify")
                if role == f"planner:{r}" or role.startswith(f"planner:{r}:")
            ),
            "other",
        )
        usage.append(
            {
                "role": f"planner:{role}",
                "model": model_label(item.get("model")),
                **{
                    key: number(item.get(key), integer=key != "estimated_usd")
                    for key in ("input_tokens", "output_tokens", "estimated_usd", "latency_ms")
                },
            }
        )
    report = {
        "schema_version": 1,
        "mode": "live",
        "scope": scope,
        "run_at": datetime.now(timezone.utc).isoformat(),
        # CLI automation cannot attest the manual fidelity/lifecycle audit.
        "passed": False,
        "status": "failed" if record.get("status") == "failed" else "incomplete",
        "failure": record.get("failure") if record.get("failure") in FAILURES else "invalid_configuration",
        "automated_checks_passed": (
            record.get("automated_checks_passed") is True and record.get("status") != "failed"
        ),
        "model_requests_possible": record.get("model_requests_possible") is True,
        "profile_qualified": record.get("profile_qualified") is True,
        "selected_model": model_label(record.get("selected_model")),
        "thinking_controls_requested": record.get("thinking_controls_requested") is True,
        "provider_controls_observed": "unverified",
        "multiple_account_inference": "unverified",
        "usage": usage,
        "codex_tokens": {
            key: number(record.get("codex_tokens", {}).get(key), integer=True)
            for key in ("inputTokens", "outputTokens", "totalTokens", "cachedInputTokens")
        },
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report
