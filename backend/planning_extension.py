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
from backend.app.planning.contracts import (
    PlanningExtension,
    PlanningFifthAttempt,
    PlanningRequalification,
    PlanningSeventhAttempt,
    PlanningSixthAttempt,
    content_hash,
)
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


def eligible(config, session, *, requalification=False, fifth_attempt=False, sixth_attempt=False,
             seventh_attempt=False):
    if sum((requalification, fifth_attempt, sixth_attempt, seventh_attempt)) > 1:
        raise ValueError("Select only one planning grant")
    if config.mode != "live" or config.planning_max_attempts != 2:
        raise ValueError("Extension requires live mode and the ordinary two-attempt policy")
    PlanningService(None, None, config).guard(session)
    state = session.planning
    if seventh_attempt:
        if state.seventh_attempt:
            raise ValueError("A seventh-attempt planning grant is already recorded")
        if (
            state.status != "blocked" or state.active or state.approval
            or not state.sixth_attempt or state.sixth_attempt.status != "consumed"
            or len(state.attempts) != 6
            or [attempt.revision for attempt in state.attempts] != [1, 2, 3, 4, 5, 6]
            or len({attempt.plan_id for attempt in state.attempts}) != 1
            or any(
                attempt.requirements_revision != session.revision or not attempt.error
                for attempt in state.attempts
            )
        ):
            raise ValueError("Seventh-attempt grant requires six failures and consumed prior grants")
        return
    if sixth_attempt:
        if state.sixth_attempt:
            raise ValueError("A sixth-attempt planning grant is already recorded")
        if (
            state.status != "blocked" or state.active or state.approval
            or not state.fifth_attempt or state.fifth_attempt.status != "consumed"
            or len(state.attempts) != 5
            or [attempt.revision for attempt in state.attempts] != [1, 2, 3, 4, 5]
            or len({attempt.plan_id for attempt in state.attempts}) != 1
            or any(
                attempt.requirements_revision != session.revision or not attempt.error
                for attempt in state.attempts
            )
        ):
            raise ValueError("Sixth-attempt grant requires five failures and consumed prior grants")
        return
    if fifth_attempt:
        if state.fifth_attempt:
            raise ValueError("A fifth-attempt planning grant is already recorded")
        if (
            state.status != "blocked" or state.active or state.approval
            or not state.extension or state.extension.status != "consumed"
            or not state.requalification or state.requalification.status != "consumed"
            or len(state.attempts) != 4
            or [attempt.revision for attempt in state.attempts] != [1, 2, 3, 4]
            or len({attempt.plan_id for attempt in state.attempts}) != 1
            or any(
                attempt.requirements_revision != session.revision or not attempt.error
                for attempt in state.attempts
            )
        ):
            raise ValueError("Fifth-attempt grant requires four failures and consumed prior grants")
        return
    if requalification:
        if state.requalification:
            raise ValueError("A planning requalification is already recorded")
        if (
            state.status != "blocked" or state.active or state.approval
            or not state.extension or state.extension.status != "consumed"
            or len(state.attempts) != 3
            or [attempt.revision for attempt in state.attempts] != [1, 2, 3]
            or len({attempt.plan_id for attempt in state.attempts}) != 1
            or any(
                attempt.requirements_revision != session.revision or not attempt.error
                for attempt in state.attempts
            )
        ):
            raise ValueError("Requalification requires three failed attempts and a consumed extension")
        return
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
        "requalification_status": (
            session.planning.requalification.status if session.planning.requalification else None
        ),
        "fifth_attempt_status": (
            session.planning.fifth_attempt.status if session.planning.fifth_attempt else None
        ),
        "sixth_attempt_status": (
            session.planning.sixth_attempt.status if session.planning.sixth_attempt else None
        ),
        "seventh_attempt_status": (
            session.planning.seventh_attempt.status if session.planning.seventh_attempt else None
        ),
    }


def preflight(config, session_id, *, requalification=False, fifth_attempt=False, sixth_attempt=False,
              seventh_attempt=False):
    session = read_session(config, session_id)
    result = summary(config, session)
    try:
        eligible(config, session, requalification=requalification,
                 fifth_attempt=fifth_attempt, sixth_attempt=sixth_attempt, seventh_attempt=seventh_attempt)
        result["eligible"] = True
    except ValueError:
        result["eligible"] = False
    return result


def issue(config, session_id, *, expected_state_hash, approval_text, reason, implementation_commit,
          requalification=False, fifth_attempt=False, sixth_attempt=False, seventh_attempt=False):
    session = read_session(config, session_id)
    if state_hash(session) != expected_state_hash:
        raise ValueError("Session changed; repeat preflight before issuing an extension")
    eligible(config, session, requalification=requalification,
             fifth_attempt=fifth_attempt, sixth_attempt=sixth_attempt, seventh_attempt=seventh_attempt)
    if seventh_attempt:
        grant_type = PlanningSeventhAttempt
        extra = {
            "sixth_attempt_id": session.planning.sixth_attempt.id,
            "sixth_attempt_hash": content_hash(
                session.planning.sixth_attempt.model_dump(mode="json", round_trip=True)
            ),
        }
    elif sixth_attempt:
        grant_type = PlanningSixthAttempt
        extra = {
            "fifth_attempt_id": session.planning.fifth_attempt.id,
            "fifth_attempt_hash": content_hash(
                session.planning.fifth_attempt.model_dump(mode="json", round_trip=True)
            ),
        }
    elif fifth_attempt:
        grant_type = PlanningFifthAttempt
        extra = {
            "requalification_id": session.planning.requalification.id,
            "requalification_hash": content_hash(
                session.planning.requalification.model_dump(mode="json", round_trip=True)
            ),
        }
    elif requalification:
        grant_type = PlanningRequalification
        extra = {
            "extension_id": session.planning.extension.id,
            "extension_hash": content_hash(
                session.planning.extension.model_dump(mode="json", round_trip=True)
            ),
        }
    else:
        grant_type, extra = PlanningExtension, {}
    grant = grant_type(
        id=str(uuid4()), session_id=session.id, requirements_revision=session.revision,
        prior_attempt_hashes=[
            content_hash(a.model_dump(mode="json", round_trip=True)) for a in session.planning.attempts
        ],
        recorded_at=datetime.now(timezone.utc), reason=reason,
        implementation_commit=implementation_commit, approval_text=approval_text,
        **extra,
    )
    if seventh_attempt:
        session.planning.seventh_attempt = grant
    elif sixth_attempt:
        session.planning.sixth_attempt = grant
    elif fifth_attempt:
        session.planning.fifth_attempt = grant
    elif requalification:
        session.planning.requalification = grant
    else:
        session.planning.extension = grant
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
    grant_mode = parser.add_mutually_exclusive_group()
    grant_mode.add_argument("--requalify", action="store_true", help="Separate one-time fourth-attempt grant")
    grant_mode.add_argument(
        "--fifth-attempt", action="store_true", help="Separate one-time fifth-attempt grant"
    )
    grant_mode.add_argument(
        "--sixth-attempt", action="store_true", help="Separate one-time sixth-attempt grant"
    )
    grant_mode.add_argument(
        "--seventh-attempt", action="store_true", help="Separate one-time seventh-attempt grant"
    )
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
                requalification=args.requalify, fifth_attempt=args.fifth_attempt,
                sixth_attempt=args.sixth_attempt, seventh_attempt=args.seventh_attempt,
            )
        else:
            result = preflight(
                config, session_id, requalification=args.requalify,
                fifth_attempt=args.fifth_attempt, sixth_attempt=args.sixth_attempt,
                seventh_attempt=args.seventh_attempt
            )
        result["status"] = "recorded" if args.issue else "preflight"
    except (ValueError, OSError, sqlite3.Error):
        result = {
            "status": "blocked", "model_requests_possible": False,
            "failure": (
                "seventh_attempt_preconditions_failed" if args.seventh_attempt else
                "sixth_attempt_preconditions_failed" if args.sixth_attempt else
                "fifth_attempt_preconditions_failed" if args.fifth_attempt else
                "requalification_preconditions_failed" if args.requalify else "extension_preconditions_failed"
            ),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
