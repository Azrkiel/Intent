import sqlite3

from ..planning.validation import overlaps
from .contracts import Run


class ExecutionStore:
    def __init__(self, sessions):
        self.sessions = sessions
        with sessions.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS execution_runs (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
                "package_id TEXT NOT NULL, plan_hash TEXT NOT NULL, "
                "status TEXT NOT NULL, state TEXT NOT NULL, "
                "UNIQUE(session_id,plan_hash,package_id))"
            )
            db.execute("DROP INDEX IF EXISTS one_active_executor")

    def claim(self, run: Run, *, capacity=1, global_capacity=1) -> Run:
        try:
            with self.sessions.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                records = [
                    Run.model_validate_json(row[0])
                    for row in db.execute("SELECT state FROM execution_runs").fetchall()
                ]

                def phase_key(r):
                    return r.session_id, r.plan.content_hash, r.package_id.split("-W")[0]

                same = [r for r in records if phase_key(r) == phase_key(run)]
                if any(r.status in {"blocked", "cancelled"} or r.stale for r in same):
                    raise ValueError("Phase is blocked; preserve work and require repair/review")
                active = [r for r in records if r.status in {"queued", "running", "verifying", "blocked"}]
                held = [r for r in records if r.status not in {"cancelled"}]
                if any(phase_key(r) != phase_key(run) for r in held):
                    raise ValueError("Another phase requires acceptance before dispatch")
                if (
                    len(active) >= global_capacity
                    or len([r for r in active if r.session_id == run.session_id]) >= capacity
                ):
                    raise ValueError("Codex worker capacity is occupied")
                for current in active:
                    if any(overlaps(a, b) for a in run.owned_paths for b in current.owned_paths) or set(
                        run.interfaces
                    ) & set(current.interfaces):
                        raise ValueError("Worker ownership or interface conflict")
                db.execute(
                    "INSERT INTO execution_runs VALUES(?,?,?,?,?,?)",
                    (
                        run.id,
                        run.session_id,
                        run.package_id,
                        run.plan.content_hash,
                        run.status,
                        run.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "A run already owns this package or the single executor; reconcile it first"
            ) from error
        return run

    def get(self, id: str) -> Run:
        with self.sessions.connect() as db:
            row = db.execute("SELECT state FROM execution_runs WHERE id=?", (id,)).fetchone()
        if row is None:
            raise KeyError(id)
        return Run.model_validate_json(row[0])

    def list(self, session_id: str) -> list[Run]:
        with self.sessions.connect() as db:
            rows = db.execute(
                "SELECT state FROM execution_runs WHERE session_id=? ORDER BY rowid DESC LIMIT 40",
                (session_id,),
            ).fetchall()
        return [Run.model_validate_json(row[0]) for row in rows]

    def patch(self, id: str, change) -> Run:
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM execution_runs WHERE id=?", (id,)).fetchone()
            if row is None:
                raise KeyError(id)
            current = Run.model_validate_json(row[0])
            change(current)
            current = Run.model_validate(current.model_dump())
            db.execute(
                "UPDATE execution_runs SET status=?,state=? WHERE id=?",
                (current.status, current.model_dump_json(), id),
            )
        return current

    def recover(self):
        with self.sessions.connect() as db:
            rows = db.execute("SELECT id FROM execution_runs WHERE status IN ('queued','running')").fetchall()
        for (id,) in rows:

            def interrupted(run):
                run.status = "blocked"
                run.error = (
                    "Server restarted. Reconcile saved thread/turn IDs; no replacement worker was launched."
                )

            self.patch(id, interrupted)
