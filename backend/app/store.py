import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .domain import Session
from .planning.allowance import state_hash
from .planning.contracts import PlanDocument


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions "
                "(id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS plans (session_id TEXT NOT NULL, plan_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, content_hash TEXT NOT NULL, content TEXT NOT NULL, "
                "PRIMARY KEY(session_id, plan_id, revision))"
            )

    def save_plan(self, session_id: str, plan: PlanDocument):
        payload = plan.model_dump_json(round_trip=True)
        with self.connect() as db:
            row = db.execute(
                "SELECT content_hash,content FROM plans WHERE session_id=? AND plan_id=? AND revision=?",
                (session_id, plan.id, plan.revision),
            ).fetchone()
            if row:
                if row != (plan.content_hash, payload):
                    raise ValueError("Plan revisions are immutable")
                return
            db.execute("INSERT INTO plans VALUES(?,?,?,?,?)",
                       (session_id, plan.id, plan.revision, plan.content_hash, payload))

    def get_plan(self, session_id: str, plan_id: str, revision: int) -> PlanDocument:
        with self.connect() as db:
            row = db.execute(
                "SELECT content_hash,content FROM plans WHERE session_id=? AND plan_id=? AND revision=?",
                (session_id, plan_id, revision),
            ).fetchone()
        if row is None:
            raise KeyError(plan_id)
        plan = PlanDocument.model_validate_json(row[1])
        if plan.content_hash != row[0]:
            raise ValueError("Plan content hash does not match")
        return plan

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            yield db

    def save(self, session: Session, *, expected_state_hash=None):
        # Round-trip mode excludes computed fields, which are output-only contracts.
        data = session.model_dump(mode="json", round_trip=True)
        Session.model_validate(data)
        payload = json.dumps(data)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM sessions WHERE id=?", (session.id,)).fetchone()
            previous = Session.model_validate_json(row[0]) if row else None
            if expected_state_hash is not None and (
                previous is None or state_hash(previous) != expected_state_hash
            ):
                raise ValueError("Session changed; repeat preflight before planning")
            if previous:
                for field in ("extension", "requalification", "fifth_attempt", "sixth_attempt"):
                    old, new = getattr(previous.planning, field), getattr(session.planning, field)
                    if not old:
                        continue
                    if (
                        new is None
                        or old.model_dump(exclude={"status"}) != new.model_dump(exclude={"status"})
                        or (old.status != "granted" and old.status != new.status)
                        or len(session.planning.attempts) < len(previous.planning.attempts)
                    ):
                        raise ValueError(f"Planning {field} and consumed attempts cannot be replaced")
                    if session.usage[:len(previous.usage)] != previous.usage:
                        raise ValueError(f"Planning {field} usage history cannot be replaced")
                if session.planning.requalification and (
                    session.planning.attempts[:3] != previous.planning.attempts[:3]
                ):
                    raise ValueError("Planning requalification prior attempts cannot be replaced")
                if session.planning.fifth_attempt and (
                    session.planning.attempts[:4] != previous.planning.attempts[:4]
                ):
                    raise ValueError("Planning fifth-attempt prior attempts cannot be replaced")
                if session.planning.sixth_attempt and (
                    session.planning.attempts[:5] != previous.planning.attempts[:5]
                ):
                    raise ValueError("Planning sixth-attempt prior attempts cannot be replaced")
            db.execute(
                "INSERT INTO sessions(id,state) VALUES(?,?) ON CONFLICT(id) DO UPDATE "
                "SET state=excluded.state, updated_at=CURRENT_TIMESTAMP",
                (session.id, payload),
            )

    def get(self, id: str) -> Session:
        with self.connect() as db:
            row = db.execute("SELECT state FROM sessions WHERE id=?", (id,)).fetchone()
        if row is None:
            raise KeyError(id)
        return Session.model_validate_json(row[0])

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,state FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT 40")
            return [
                {"id": id, "title": json.loads(state)["title"], "mode": json.loads(state)["mode"]}
                for id, state in rows
            ]

    def recover(self):
        """A server restart must not leave a build marked running forever."""
        with self.connect() as db:
            rows = db.execute("SELECT state FROM sessions").fetchall()
        for (raw,) in rows:
            session = Session.model_validate_json(raw)
            changed = False
            if session.build.status == "running":
                session.build.status = "failed"
                session.build.logs.append("Server restarted. Start a new build to retry.")
                changed = True
            if session.planning.status == "planning":
                session.planning.status = "blocked"
                session.planning.approval = None
                if session.planning.attempts:
                    session.planning.attempts[-1].error = (
                        "Server restarted. Sections and usage were preserved."
                    )
                changed = True
            if changed:
                self.save(session)
