import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


@pytest.fixture
def vault_client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "vault.db"), mode="demo")
    with TestClient(create_app(settings)) as client:
        session = client.post("/api/sessions", json={}).json()
        yield client, f"/api/sessions/{session['id']}/vault", settings


def archive(files):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, content in files.items():
            bundle.writestr(path, content)
    return result.getvalue()


def test_vault_persists_without_mutating_session_and_conflicts_are_atomic(vault_client):
    client, base, settings = vault_client
    session_url = base.removesuffix("/vault")
    before = client.get(session_url).json()
    document = client.get(base).json()
    assert document["revision"] == 0
    assert document["notes"][0]["id"] == "plan"
    document["notes"][0]["body"] = "# Plan\n\n[[Ideas]]"
    document["notes"].append({"id": "idea", "path": "Ideas.md", "body": "# Ideas", "kind": "note"})
    saved = client.post(base, json={"expected_revision": 0, "notes": document["notes"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert client.post(base, json={"expected_revision": 0, "notes": document["notes"]}).status_code == 409
    assert client.get(session_url).json() == before
    with TestClient(create_app(settings)) as restored:
        assert restored.get(base).json() == saved.json()


@pytest.mark.parametrize(
    "path",
    [
        "../escape.md",
        "C:/escape.md",
        "/root.md",
        "a\\b.md",
        "NUL.md",
        "a/COM1.md",
        "a./note.md",
        "a:stream.md",
        ".obsidian/a.md",
        "note.txt",
    ],
)
def test_unsafe_note_paths_are_rejected(vault_client, path):
    client, base, _ = vault_client
    notes = client.get(base).json()["notes"]
    notes[0]["path"] = path
    assert client.post(base, json={"expected_revision": 0, "notes": notes}).status_code == 422


def test_root_and_case_insensitive_unique_paths_are_required(vault_client):
    client, base, _ = vault_client
    root = client.get(base).json()["notes"][0]
    assert client.post(base, json={"expected_revision": 0, "notes": []}).status_code == 422
    duplicate = {**root, "id": "other", "kind": "note", "path": root["path"].upper()}
    assert client.post(base, json={"expected_revision": 0, "notes": [root, duplicate]}).status_code == 422
    assert client.get(base).json()["revision"] == 0


def test_export_import_round_trip_and_plan_approval_is_unchanged(vault_client):
    client, base, _ = vault_client
    notes = [
        {"id": "plan", "path": "Main.md", "kind": "plan", "body": "# My plan\n\n[[notes/Idea]]"},
        {"id": "idea", "path": "notes/Idea.md", "kind": "note", "body": "# Idea\n\n[Back](../Main.md)"},
    ]
    assert client.post(base, json={"expected_revision": 0, "notes": notes}).status_code == 200
    result = client.get(base + "/export")
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as bundle:
        assert set(bundle.namelist()) == {"Main.md", "notes/Idea.md", "intent-vault.json"}
        assert json.loads(bundle.read("intent-vault.json"))["root_path"] == "Main.md"
    session_before = client.get(base.removesuffix("/vault")).json()
    imported = client.post(
        base + "/import?expected_revision=1",
        content=result.content,
        headers={"Content-Type": "application/zip"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["revision"] == 2
    assert {n["path"]: n["body"] for n in imported.json()["notes"]} == {n["path"]: n["body"] for n in notes}
    assert imported.json()["source"] is None
    assert client.get(base.removesuffix("/vault")).json() == session_before


@pytest.mark.parametrize(
    "files",
    [
        {"../escape.md": "bad"},
        {"A.md": "one", "a.md": "two"},
        {"big.md": "a" * 100_001},
        {"a.md": b"\xff"},
        {"script.html": "<script/>"},
        {".obsidian/a.md": "hidden"},
        {"a.md": "a", "intent-vault.json": '{"root_path":"missing.md"}'},
    ],
)
def test_invalid_import_never_replaces_saved_content(vault_client, files):
    client, base, _ = vault_client
    before = client.get(base).json()
    result = client.post(
        base + "/import?expected_revision=0",
        content=archive(files),
        headers={"Content-Type": "application/zip"},
    )
    assert result.status_code in {413, 422}, result.text
    assert client.get(base).json() == before


def test_import_rejects_stale_revision_unknown_session_and_cross_origin(vault_client):
    client, base, _ = vault_client
    payload = archive({"Plan.md": "# Imported"})
    assert client.post(base + "/import?expected_revision=5", content=payload).status_code == 409
    assert client.get("/api/sessions/unknown/vault").status_code == 404
    assert (
        client.post(
            base + "/import?expected_revision=0", content=payload, headers={"Origin": "https://other.test"}
        ).status_code
        == 403
    )


def test_seed_requires_a_plan_and_never_overwrites_user_notes(vault_client):
    client, base, _ = vault_client
    assert client.post(base + "/seed", json={"expected_revision": 0}).status_code == 409


def test_seed_links_canonical_plan_and_preserves_it_after_note_edits(vault_client):
    from backend.tests.planning_fixtures import ready_session
    from backend.tests.test_planning_api import generate

    client, _, _ = vault_client
    session = ready_session()
    client.app.state.store.save(session)
    detail = generate(client, session)
    base = f"/api/sessions/{session.id}/vault"
    result = client.post(base + "/seed", json={"expected_revision": 0})
    assert result.status_code == 200, result.text
    vault = result.json()
    assert vault["source"]["content_hash"] == detail["plan"]["content_hash"]
    assert {"plan", "phase", "package", "task", "spec", "screen"} <= {n["kind"] for n in vault["notes"]}
    root = next(n for n in vault["notes"] if n["id"] == "plan")
    assert "DEMO" in root["body"] and "Phase-1.md" in root["body"]
    root["body"] += "\nMy own changes"
    assert client.post(base, json={"expected_revision": 1, "notes": vault["notes"]}).status_code == 200
    assert client.post(base + "/seed", json={"expected_revision": 2}).status_code == 409
    assert client.get(f"/api/sessions/{session.id}/plan").json() == detail


def test_seed_resolves_root_links_when_main_note_is_in_a_folder(vault_client):
    from backend.tests.planning_fixtures import ready_session
    from backend.tests.test_planning_api import generate

    client, _, _ = vault_client
    session = ready_session()
    client.app.state.store.save(session)
    generate(client, session)
    base = f"/api/sessions/{session.id}/vault"
    notes = client.get(base).json()["notes"]
    notes[0]["path"] = "project/Main.md"
    client.post(base, json={"expected_revision": 0, "notes": notes})
    result = client.post(base + "/seed", json={"expected_revision": 1}).json()
    root = next(n for n in result["notes"] if n["id"] == "plan")
    assert "(../Vision.md)" in root["body"]


def test_symlink_and_oversized_archive_are_rejected(vault_client):
    import stat

    client, base, _ = vault_client
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as bundle:
        entry = zipfile.ZipInfo("Link.md")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(entry, "../elsewhere")
    assert client.post(base + "/import?expected_revision=0", content=result.getvalue()).status_code == 422
    assert client.post(base + "/import?expected_revision=0", content=b"x" * 3_000_001).status_code == 413


def test_multibyte_note_limit_and_forged_source_are_rejected(vault_client):
    client, base, _ = vault_client
    notes = client.get(base).json()["notes"]
    notes[0]["body"] = "界" * 40_000
    assert client.post(base, json={"expected_revision": 0, "notes": notes}).status_code == 422
    notes[0]["body"] = "# Allowed"
    assert client.post(base, json={"expected_revision": 0, "notes": notes, "source": {}}).status_code == 422


def test_configured_loopback_frontend_port_can_save(tmp_path):
    settings = Settings(database_path=str(tmp_path / "port.db"), mode="demo", frontend_port=3001)
    with TestClient(create_app(settings)) as client:
        session = client.post("/api/sessions", json={}).json()
        base = f"/api/sessions/{session['id']}/vault"
        notes = client.get(base).json()["notes"]
        response = client.post(
            base, json={"expected_revision": 0, "notes": notes}, headers={"Origin": "http://127.0.0.1:3001"}
        )
        assert response.status_code == 200
