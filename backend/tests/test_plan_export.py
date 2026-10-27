import hashlib
import io
import json
import zipfile

import pytest

from backend.app.planning.contracts import PlanApproval, PlanDocument
from backend.app.planning.export import export_bundle
from backend.tests.test_plan_validation import plan


def approval(doc):
    return PlanApproval(
        plan_id=doc.id,
        revision=doc.revision,
        content_hash=doc.content_hash,
        requirements_revision=doc.requirements_revision,
    )


def test_bundle_inventory_hashes_and_deterministic_bytes():
    session, doc = plan()
    data = export_bundle(doc, approval(doc), session.revision, session.ledger)
    assert data == export_bundle(doc, approval(doc), session.revision, session.ledger)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert {
            "plan.json",
            "manifest.json",
            "VISION.md",
            "SPEC.md",
            "WIREFRAMES.txt",
            "ARCHITECTURE.txt",
            "AGENTS.md",
            "CLAUDE.md",
            "phases/P1/work-packages/P1-W1/TASK.md",
        } <= set(names)
        manifest = json.loads(archive.read("manifest.json"))
        restored = PlanDocument.model_validate_json(archive.read("plan.json"))
        assert restored == doc and restored.content_hash == manifest["content_hash"]
        for entry in manifest["artifacts"]:
            if entry["path"] != "manifest.json":
                assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
        rules = archive.read("AGENTS.md").decode()
        assert "not alone" in rules and "permissions" in rules
        assert "AGENTS.md" in archive.read("CLAUDE.md").decode()
        assert session.id.encode() not in data


def test_missing_stale_or_tampered_approval_cannot_export():
    session, doc = plan()
    accepted = approval(doc)
    for supplied, revision in [(None, 1), (accepted, 2)]:
        with pytest.raises(ValueError):
            export_bundle(doc, supplied, revision, session.ledger)
    doc.outline.vision.text = "Changed"
    with pytest.raises(ValueError):
        export_bundle(doc, accepted, 1, session.ledger)


def test_model_text_cannot_become_archive_path():
    session, doc = plan()
    doc.outline.phases[0].title = "../../AGENTS.md"
    with zipfile.ZipFile(io.BytesIO(export_bundle(doc, approval(doc), 1, session.ledger))) as archive:
        assert not any(".." in name for name in archive.namelist())


def test_export_provenance_is_part_of_approved_hash():
    session, doc = plan()
    accepted = approval(doc)
    doc.sources[0].source = "Tampered source quote"
    with pytest.raises(ValueError):
        export_bundle(doc, accepted, 1, session.ledger)
