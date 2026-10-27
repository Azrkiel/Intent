from backend.app.domain import Brief, BriefLine
from backend.evals.run import keyword_hits, load_fixtures, unsupported_lines
from backend.tests.test_ledger import candidate, ready_session


def test_evaluation_has_eight_prompts_with_two_or_three_planted_gaps_each():
    fixtures = load_fixtures()
    assert len(fixtures) == 8
    assert len({item["id"] for item in fixtures}) == 8
    assert all(2 <= len(item["ambiguities"]) <= 3 for item in fixtures)


def test_keyword_metric_counts_each_planted_gap_once_and_is_a_proxy():
    ambiguities = [
        {"id": "storage", "keywords": ["data", "storage"]},
        {"id": "access", "keywords": ["account", "login"]},
    ]
    questions = [candidate(divergence=3, uncertainty=3, cost_to_change=3)] * 2
    assert keyword_hits(questions, ambiguities) == ["storage"]


def test_evaluation_reports_untraceable_lines_instead_of_silently_calling_them_valid():
    session = ready_session()
    session.brief = Brief(
        lines=[
            BriefLine(section="Goal", text="Source", ledger_ids=["L1"]),
            BriefLine(section="Made up", text="Untraceable", ledger_ids=["L99"]),
        ]
    )
    assert unsupported_lines(session) == 1
