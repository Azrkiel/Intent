import json

from backend.smoke_report import write_report


def test_empty_report_is_not_a_success(tmp_path):
    output = tmp_path / "empty.json"
    assert not write_report(output, [], False)["passed"]
    assert json.loads(output.read_text())["mode"] == "live"


def test_report_keeps_usage_but_drops_unapproved_fields(tmp_path):
    output = tmp_path / "nested" / "basic.json"
    usage = dict(
        role="extractor",
        model="nano",
        input_tokens=20,
        output_tokens=10,
        estimated_usd=0.000004,
        latency_ms=100,
    )
    record = dict(
        model="nano",
        passed=False,
        failure="model_error",
        grounded_items=0,
        usage=[usage],
        api_key="test-secret",
        raw_response="test-secret",
        error="test-secret",
    )
    report = write_report(output, [record], True)
    assert not report["passed"]
    assert report["thinking_controls_requested"] is True
    assert report["results"][0]["usage"] == [usage]
    assert "test-secret" not in output.read_text()
