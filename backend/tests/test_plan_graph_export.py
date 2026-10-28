import hashlib
import io
import json
import zipfile

from backend.app.planning.export import export_bundle
from backend.app.planning.graph_export import graph_files
from backend.tests.test_plan_export import approval
from backend.tests.test_plan_validation import plan


def test_human_export_keeps_complete_inventory_and_hashes_graph_members():
    session, document = plan()
    raw = export_bundle(document, approval(document), session.revision, session.ledger)
    assert raw == export_bundle(document, approval(document), session.revision, session.ledger)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert {
            "plan.json", "graph/graph.json", "graph/index.html", "graph/nodes/root.json",
        } <= set(archive.namelist())
        graph = json.loads(archive.read("graph/graph.json"))
        assert graph["source"]["content_hash"] == document.content_hash
        for node in graph["nodes"]:
            assert json.loads(archive.read(f"graph/nodes/{node['id']}.json")) == node
        manifest = json.loads(archive.read("manifest.json"))
        for entry in manifest["artifacts"]:
            if entry["path"].startswith("graph/"):
                assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
        assert "phases/P2/work-packages/P2-W1/TASK.md" in archive.namelist()


def test_offline_viewer_escapes_script_closers_and_uses_no_remote_resources():
    session, document = plan()
    hostile = '</script><img src=x onerror=alert(1)><script>evil()</script>'
    document.outline.vision.text = hostile
    files = graph_files(document, session.ledger, state="approved")
    html = files["graph/index.html"]
    assert hostile not in html
    assert "\\u003c/script\\u003e" in html
    assert json.loads(files["graph/graph.json"])["nodes"][0]["body"]["outline"]["vision"]["text"] == hostile
    assert '<script src=' not in html and '<link href="http' not in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "textContent" in html and "innerHTML" not in html
    assert 'Content-Security-Policy' in html
    assert "Center root" in html and "Search plan" in html
    assert "DEMO" in html
    assert "keydown" in html


def test_export_graph_can_use_the_current_execution_worker_limits():
    session, document = plan()
    limits = {"per_session": 2, "global": 2}
    data = export_bundle(document, approval(document), session.revision, session.ledger, worker_limits=limits)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        graph = json.loads(archive.read("graph/graph.json"))
        assert graph["nodes"][0]["body"]["orchestration"]["worker_limits"] == limits
