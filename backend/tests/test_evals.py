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


def test_run_cap_limits_each_session_to_the_remaining_total_and_stops(monkeypatch, tmp_path):
    import asyncio

    import pytest

    from backend.evals import run as evals

    budgets = []

    async def fake_case(fixture, settings, models, store, strategy, clarity_version=1):
        budgets.append(settings.session_budget_usd)
        return {"fixture": fixture["id"], "ready": True, "error": None, "questions_to_ready": 1,
                "calls": 1, "estimated_usd": 0.4}

    monkeypatch.setattr(evals, "run_case", fake_case)
    with pytest.raises(SystemExit):
        asyncio.run(evals.run(True, str(tmp_path / "r.json"), max_total_usd=1.0, strategies=["lenses"]))
    assert budgets == [1.0, pytest.approx(0.6), pytest.approx(0.2)]


async def test_schema_failure_raw_output_lands_in_the_case_result(tmp_path):
    import httpx
    from openai import AsyncOpenAI

    from backend.app.models import LiveModels
    from backend.app.settings import Settings
    from backend.app.store import Store
    from backend.evals.run import run_case
    from backend.tests.test_models import completion

    client = AsyncOpenAI(
        api_key="test", base_url="https://test.invalid/v1", max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=completion("{oops")))
        ),
    )
    settings = Settings(mode="live", send_thinking_controls=False)
    result = await run_case(
        load_fixtures()[0], settings, LiveModels(settings, client=client),
        Store(str(tmp_path / "e.sqlite3")), "single",
    )
    assert "JSON parsing" in result["error"]
    assert result["raw_failures"] == [{"role": "extractor", "category": "JSON parsing", "raw": "{oops"}]
    await client.close()


def test_v2_simulated_user_picks_the_closest_draft_and_v1_still_types():
    from backend.app.clarity.northstar import KEEP
    from backend.evals.run import answer_for

    fixture = load_fixtures()[0]
    answer = fixture["ambiguities"][0]["answer"]
    question = candidate(divergence=3, uncertainty=3, cost_to_change=3).model_copy(update={
        "lens": "north-star", "suggestion": True,
        "options": ["Something unrelated entirely", answer + " today", KEEP],
    })
    assert answer_for(question, fixture, 2) == answer + " today"
    assert answer_for(question, fixture, 1) != answer + " today"
    decision = question.model_copy(update={"lens": "decision", "suggestion": False})
    assert answer_for(decision, fixture, 2) == answer + " today"


async def test_v2_case_records_each_round_of_north_star_state(tmp_path):
    from backend.app.demo import DemoModels
    from backend.app.settings import Settings
    from backend.app.store import Store
    from backend.evals.run import load_fixtures, run_case

    fixture = load_fixtures()[0]
    store = Store(str(tmp_path / "eval.db"))
    result = await run_case(fixture, Settings(mode="demo"), DemoModels(), store, "lenses", clarity_version=2)
    assert result["rounds"] and result["rounds"][0]["answer"] == fixture["prompt"]
    who = result["rounds"][-1]["fields"]["who-when"]
    assert set(who) == {"text", "failing", "reasons"}
