import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.domain import Usage


def write_report(output, records, thinking_controls):
    allowed_failures = {"missing_credentials", "model_error", "ledger_validation"}
    results = []
    for record in records:
        failure = record.get("failure")
        results.append(
            {
                "model": record["model"],
                "passed": bool(record["passed"]),
                "grounded_items": int(record.get("grounded_items", 0)),
                "failure": failure if failure in allowed_failures else None,
                "usage": [Usage.model_validate(item).model_dump() for item in record.get("usage", [])],
            }
        )
    report = {
        "mode": "live",
        "scope": "protocol_smoke_not_quality_evaluation",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "thinking_controls_requested": bool(thinking_controls),
        "passed": bool(results) and all(item["passed"] for item in results),
        "results": results,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
