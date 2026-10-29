from ..store import Store
from .contracts import Note, Vault


class VaultConflict(ValueError):
    pass


class VaultStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS vaults "
                "(session_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, content TEXT NOT NULL)"
            )

    def get(self, session) -> Vault:
        with self.store.connect() as db:
            row = db.execute("SELECT content FROM vaults WHERE session_id=?", (session.id,)).fetchone()
        return (
            Vault.model_validate_json(row[0])
            if row
            else Vault(
                revision=0,
                demo=session.mode == "demo",
                notes=[
                    Note(
                        id="plan",
                        kind="plan",
                        path="Plan.md",
                        body=f"# {session.title}\n\nWrite your plan here. Connect notes with `[[Note name]]` "
                        "or `[a Markdown link](Notes.md)`.\n",
                    )
                ],
            )
        )

    def save(self, session_id: str, expected_revision: int, vault: Vault) -> Vault:
        saved = vault.model_copy(update={"revision": expected_revision + 1})
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM vaults WHERE session_id=?", (session_id,)).fetchone()
            actual = row[0] if row else 0
            if actual != expected_revision:
                raise VaultConflict("This vault changed in another window. Your draft has not been saved.")
            db.execute(
                "INSERT INTO vaults VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE "
                "SET revision=excluded.revision,content=excluded.content",
                (session_id, saved.revision, saved.model_dump_json()),
            )
        return saved
