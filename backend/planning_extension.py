"""Read-only preflight or explicit local issuance of one planning extension.

Stop the app server before issuance. This command never constructs a provider.
"""

import argparse
import json
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.domain import Session
from backend.app.planning.allowance import state_hash
from backend.app.planning.contracts import PlanningExtension, content_hash
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store


def read_session(config, session_id):
    uri = Path(config.database_path).resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        row = db.execute("SELECT state FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Retained session not found")
        return Session.model_validate_json(row[0])
    finally:
        db.close()


def eligible(config, session):
    if config.mode != "live" or config.planning_max_attempts != 2:
        raise ValueError("Extension requires live mode and the ordinary two-attempt policy")
    PlanningService(None, None, config).guard(session)
    state = session.planning
    if state.extension:
        raise ValueError("A planning extension is already recorded")
    if (
        state.status != "blocked" or state.active or state.approval
        or len(state.attempts) != 2
        or [a.revision for a in state.attempts] != [1, 2]
        or state.attempts[0].plan_id != state.attempts[1].plan_id
        or any(a.requirements_revision != session.revision or not a.error for a in state.attempts)
    ):
        raise ValueError("Extension requires two failed attempts for the current approved requirements")


def summary(config, session):
    grant = session.planning.extension
    return {
        "model_requests_possible": False,
        "state_hash": state_hash(session),
        "requirements_revision": session.revision,
        "attempts_consumed": len(session.planning.attempts),
        "attempt_limit": PlanningService(None, None, config).attempt_limit(session),
        "extension_status": grant.status if grant else None,
    }


def preflight(config, session_id):
    session = read_session(config, session_id)
    result = summary(config, session)
    try:
        eligible(config, session)
        result["eligible"] = True
    except ValueError:
        result["eligible"] = False
    return result


def issue(config, session_id, *, expected_state_hash, approval_text, reason, implementation_commit):
    session = read_session(config, session_id)
    if state_hash(session) != expected_state_hash:
        raise ValueError("Session changed; repeat preflight before issuing an extension")
    eligible(config, session)
    session.planning.extension = PlanningExtension(
        id=str(uuid4()), session_id=session.id, requirements_revision=session.revision,
        prior_attempt_hashes=[
            content_hash(a.model_dump(mode="json", round_trip=True)) for a in session.planning.attempts
        ],
        recorded_at=datetime.now(timezone.utc), reason=reason,
        implementation_commit=implementation_commit, approval_text=approval_text,
    )
    Store(config.database_path).save(session, expected_state_hash=expected_state_hash)
    return summary(config, session)


def require_server_stopped():
    with socket.socket() as probe:
        probe.settimeout(0.25)
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            raise ValueError("Stop the app server before issuing an extension")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session-id")
    source.add_argument("--session-id-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue", action="store_true")
    parser.add_argument("--expected-state-hash")
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--reason")
    parser.add_argument("--implementation-commit")
    args = parser.parse_args(argv)
    try:
        config = Settings()
        session_id = args.session_id or args.session_id_file.read_text(encoding="utf-8").strip()
        if args.issue:
            required = (args.expected_state_hash, args.approval_file, args.reason, args.implementation_commit)
            if not all(required):
                raise ValueError("Issuance requires preflight hash, approval file, reason, and commit")
            require_server_stopped()
            result = issue(
                config, session_id, expected_state_hash=args.expected_state_hash,
                approval_text=args.approval_file.read_text(encoding="utf-8").strip(),
                reason=args.reason, implementation_commit=args.implementation_commit,
            )
        else:
            result = preflight(config, session_id)
        result["status"] = "recorded" if args.issue else "preflight"
    except (ValueError, OSError, sqlite3.Error):
        result = {"status": "blocked", "model_requests_possible": False,
                  "failure": "extension_preconditions_failed"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
