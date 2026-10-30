from backend.app.clarity.contracts import ClarityState, FieldState, ReviewState
from backend.app.clarity.metrics import clarity_metrics
from backend.tests.clarity_fixtures import reading_queue_session


def test_metrics_report_fields_alpha_review_and_waste():
    session = reading_queue_session(answered=False)
    session.clarity = ClarityState(
        revision=1,
        source_hash="a" * 64,
        mode="live",
        fields=[FieldState(field="job", alpha=0.9, passed=True)],
        review=ReviewState(recall=1.0, critical_recall=1.0, trusted=True),
    )
    metrics = clarity_metrics(session)
    assert metrics["fields_passed"] == 1 and metrics["alpha"] == {"job": 0.9}
    assert metrics["review_recall"] == 1.0 and metrics["wasted_questions"] == [0, 0]


def test_metrics_are_none_for_v1():
    session = reading_queue_session()
    session.clarity_version = 1
    assert clarity_metrics(session) is None
