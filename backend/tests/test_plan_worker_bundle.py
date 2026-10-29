import hashlib
import io
import json
import zipfile

import pytest

from backend.app.planning.context import build_context
from backend.app.planning.worker_bundle import export_worker_bundle
from backend.tests.test_plan_context import BASE, dependency_plan, scoped_plan


def test_worker_archive_is_deterministic_scoped_and_all_members_are_hashed():
    session, doc = scoped_plan()
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    data = export_worker_bundle(packet)
    assert data == export_worker_bundle(packet)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert names == {
            "AGENTS.md", "ROOT.json", "PHASE.json", "TASK.md", "CONTEXT.md", "HANDOFF.json", "manifest.json"
        }
        assert not {"plan.json", "graph/graph.json", "VISION.md"} & names
        text = "\n".join(archive.read(n).decode("utf-8") for n in names)
        assert "OWN local step" in text
        assert "SIBLING_SENTINEL" not in text and "COUSIN_SENTINEL" not in text
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest == packet.manifest
        assert set(entry["path"] for entry in manifest["artifacts"]) == names - {"manifest.json"}
        for entry in manifest["artifacts"]:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
        handoff = json.loads(archive.read("HANDOFF.json"))
        assert handoff["status"] == "planned"
        assert {"changed_paths", "artifact_hashes", "trusted_evidence", "integrated_commit"} <= set(
            handoff["required_fields"]
        )


def test_shared_artifact_paths_are_app_generated_and_exact_unicode_bytes_preserved():
    session, doc, consumer, snapshot = dependency_plan()
    value = "保存 </script> & credentials are not permissions"
    snapshot["documents"]["contracts.py"] = value
    snapshot["artifacts"]["contracts.py"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
    packet = build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot])
    with zipfile.ZipFile(io.BytesIO(export_worker_bundle(packet))) as archive:
        assert archive.read("shared/S1/artifact-1.txt").decode("utf-8") == value
        assert "contracts.py" not in archive.namelist()


def test_worker_export_refuses_tampered_packet_instead_of_rehashing_it():
    session, doc = scoped_plan()
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    packet.documents["../secret"] = "private"
    with pytest.raises(ValueError, match="integrity"):
        export_worker_bundle(packet)
