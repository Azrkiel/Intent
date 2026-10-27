from backend.app.planning.render import render_engineering, render_human, render_package
from backend.tests.test_plan_validation import plan


def test_views_and_packets_share_identity_and_keep_choices_visible():
    _, doc = plan()
    for rendered in [
        render_human(doc),
        render_engineering(doc),
        render_package(doc, doc.phases[0].packages[0]),
    ]:
        assert doc.id in rendered and doc.content_hash in rendered
        assert "revision 1" in rendered and "DEMO" in rendered
    human = render_human(doc)
    assert "Use Python" in human and "proposal" in human
    assert "error" in human and "[L1]" in human
    engineering = render_engineering(doc)
    assert "P1-W1-T1" in engineering and "P2-W1" in engineering
