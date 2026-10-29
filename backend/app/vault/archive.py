import io
import json
import stat
import zipfile
from uuid import uuid4

from .contracts import MAX_NOTE_BYTES, MAX_NOTES, MAX_VAULT_BYTES, Note, Vault, note_path

MAX_ARCHIVE_BYTES = 3_000_000


def export_vault(vault: Vault) -> bytes:
    result = io.BytesIO()
    manifest = {
        "format": "intent-markdown-vault-v1",
        "revision": vault.revision,
        "root_path": next(n.path for n in vault.notes if n.id == "plan"),
        "source": vault.source.model_dump() if vault.source else None,
        "source_status": vault.source_status,
        "demo": vault.demo,
        "notice": "Editable notes; not an approved execution bundle.",
        "notes": [{"path": n.path, "kind": n.kind} for n in vault.notes],
    }
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as bundle:
        for note in sorted(vault.notes, key=lambda n: n.path.casefold()):
            bundle.writestr(note.path, note.body.encode("utf-8"))
        bundle.writestr("intent-vault.json", json.dumps(manifest, ensure_ascii=False))
    return result.getvalue()


def import_vault(data: bytes, *, demo: bool) -> Vault:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP exceeds the 3 MB upload limit")
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        entries = bundle.infolist()
        if len(entries) > MAX_NOTES + 100:
            raise ValueError("Too many archive entries")
        if sum(e.file_size for e in entries) > MAX_VAULT_BYTES + MAX_NOTE_BYTES:
            raise ValueError("Archive exceeds the 2 MB Markdown limit")
        names, files, manifest = set(), [], {}
        for entry in entries:
            path = entry.filename
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError("Links and encrypted entries are unsupported")
            if entry.is_dir():
                note_path(path.rstrip("/") + "/directory.md")
                continue
            if path.casefold() in names:
                raise ValueError("Duplicate archive path")
            names.add(path.casefold())
            if entry.file_size > MAX_NOTE_BYTES:
                raise ValueError("An archive member exceeds 100 KB")
            if path == "intent-vault.json":
                manifest = json.loads(bundle.read(entry).decode("utf-8"))
                if not isinstance(manifest, dict):
                    raise ValueError("Invalid vault manifest")
            else:
                note_path(path)
                files.append((path, bundle.read(entry).decode("utf-8")))
        if not files:
            raise ValueError("Import at least one Markdown note")
        root = manifest.get("root_path") or next(
            (p for p, _ in files if p.casefold() == "plan.md"), files[0][0]
        )
        if root not in {p for p, _ in files}:
            raise ValueError("The manifest root note is missing")
        kinds = {
            n["path"]: n.get("kind", "note")
            for n in manifest.get("notes", [])
            if isinstance(n, dict) and isinstance(n.get("path"), str)
        }
        return Vault(
            revision=0,
            demo=demo,
            notes=[
                Note(
                    id="plan" if p == root else uuid4().hex,
                    path=p,
                    body=b,
                    kind="plan"
                    if p == root
                    else (kinds.get(p, "note") if kinds.get(p) != "plan" else "note"),
                )
                for p, b in files
            ],
        )
