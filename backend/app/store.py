import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .domain import Session


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

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            yield db

    def save(self, session: Session):
        # Round-trip mode excludes computed fields, which are output-only contracts.
        payload = json.dumps(session.model_dump(mode="json", round_trip=True))
        with self.connect() as db:
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
            if session.build.status == "running":
                session.build.status = "failed"
                session.build.logs.append("Server restarted. Start a new build to retry.")
                self.save(session)
