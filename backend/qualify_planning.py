"""Explicit planning probe against an existing, requirements-approved live session."""

import argparse
import asyncio
import json
from pathlib import Path

from backend.app.models import LiveModels
from backend.app.planning.export import export_bundle
from backend.app.planning.render import render_engineering, render_human
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.qualification_report import write_report


async def run(output, *, session_id=None, settings=None, factory=LiveModels):
    record = {"failure": "missing_credentials"}
    provider, session = None, None
    try:
        config = settings or Settings(mode="live")
        record["thinking_controls_requested"] = config.send_thinking_controls
        key = config.nebius_api_key
        if not key or not key.get_secret_value():
            print("No model requests: configured NEBIUS_API_KEY is missing.")
        elif not session_id:
            print("No model requests: supply --session-id for approved live requirements.")
            record["failure"] = "approved_session_required"
        else:
            store = Store(config.database_path)
            session = store.get(session_id)
            # Guard before constructing any provider; keep existing allowances and approvals.
            service = PlanningService(store, None, config)
            service.guard(session)
            cached = session.planning.status in {"review_ready", "approved"} and session.planning.active
            print(
                "No model requests: inspect saved plan."
                if cached
                else "Model requests: bounded Nemotron planning; configured session budget applies."
            )
            record["model_requests_possible"] = not bool(cached)
            provider = factory(config)
            service.models = provider
            async for _ in service.generate(session):
                pass
            if session.planning.status not in {"review_ready", "approved"}:
                record.update(status="failed", failure="planning_failed")
            else:
                identity = session.planning.active
                plan = store.get_plan(session.id, identity.plan_id, identity.revision)
                root = Path(output).parent
                root.mkdir(parents=True, exist_ok=True)
                # Product content stays in separate local artifacts, never the redacted report.
                (root / "planning-human.md").write_text(render_human(plan), encoding="utf-8")
                (root / "planning-engineering.md").write_text(render_engineering(plan), encoding="utf-8")
                record.update(automated_checks_passed=True, failure="plan_review_required")
                if session.planning.status == "approved":
                    bundle = export_bundle(plan, session.planning.approval, session.revision, session.ledger)
                    (root / "planning-bundle.zip").write_bytes(bundle)
                    record["failure"] = "manual_audit_required"
    except Exception:
        record.update(status="failed", failure="planning_failed")
    finally:
        if session:
            record["usage"] = [
                item.model_dump() for item in session.usage if item.role.startswith("planner:")
            ]
        if provider:
            try:
                await provider.close()
            except Exception:
                record.update(status="failed", failure="cleanup_failed")
    return write_report(output, "planning_integration_not_quality_evaluation", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".data/live-check/planning.json")
    parser.add_argument("--session-id", help="Existing live session; stop the app server first")
    args = parser.parse_args()
    report = asyncio.run(run(args.output, session_id=args.session_id))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["automated_checks_passed"] else 1)


if __name__ == "__main__":
    main()
