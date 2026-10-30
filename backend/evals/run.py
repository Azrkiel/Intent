import argparse
import asyncio
import json
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.app.clarity.metrics import clarity_metrics
from backend.app.demo import DemoModels
from backend.app.domain import Session, gate_for
from backend.app.engine import Engine
from backend.app.models import LiveModels, ModelError
from backend.app.settings import Settings
from backend.app.store import Store


def load_fixtures():
    return json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))


def keyword_hits(questions, ambiguities):
    # Lexical screening only. The full questions/code differences are retained for human scoring.
    text = " ".join(q.question + " " + q.code_diff for q in questions).casefold()
    return [gap["id"] for gap in ambiguities if any(word.casefold() in text for word in gap["keywords"])]


def unsupported_lines(session):
    if not session.brief:
        return 0
    known = {item.id for item in session.ledger}
    return sum(not line.ledger_ids or not set(line.ledger_ids) <= known for line in session.brief.lines)


def answer_for(question, fixture):
    text = (question.question + " " + question.code_diff).casefold()
    matches = [
        (sum(word.casefold() in text for word in gap["keywords"]), gap) for gap in fixture["ambiguities"]
    ]
    best = max(matches, key=lambda pair: pair[0])
    if best[0]:
        return best[1]["answer"]
    defaults = {
        "goal": fixture["prompt"],
        "core-flow": "Create a record, edit it, then view the saved result.",
        "data": "Persist records in SQLite on the local server; keep them until I explicitly delete them.",
        "access": "One local user, with no account system in version one.",
        "non-goals": "No payments, native mobile apps, or external integrations in version one.",
        "success-criterion": "Create and edit a record, reload, "
        "and verify the same saved values are visible.",
    }
    return defaults.get(question.slot, question.options[0])


async def run_case(fixture, settings, models, store, strategy, clarity_version=1):
    session = Session(mode=settings.mode, clarity_version=clarity_version)
    store.save(session)
    engine = Engine(store, models, critic_mode=strategy)
    text = fixture["prompt"]
    error = None
    for _ in range(13):
        async for event in engine.turn(session, text):
            if event["type"] == "error":
                error = event["message"]
        if session.clarity_version == 2 and session.clarity:
            # Simulated user: confirms every read-back that is the only failing check.
            for field in list(session.clarity.fields):
                if field.failing == ["G3"]:
                    await engine.confirm_readback(session, field.field, field.text_hash)
        if error or session.warnings:
            error = error or "; ".join(session.warnings)
            break
        if gate_for(session).ready or not session.current_question:
            break
        text = answer_for(session.current_question, fixture)
    ready = gate_for(session).ready
    if ready and not error:
        try:
            if session.clarity_version == 1:
                await engine.playback(session)
            session.approved_revision = session.revision
            await engine.compile(session)
        except ModelError as cause:
            error = str(cause)
    questions = [entry.question for entry in session.questions]
    return {
        "fixture": fixture["id"],
        "strategy": strategy,
        "ready": ready,
        "error": error,
        "questions_to_ready": len(questions) if ready else None,
        "keyword_hits_requires_manual_review": keyword_hits(questions, fixture["ambiguities"]),
        "planted_ambiguities": fixture["ambiguities"],
        "structurally_untraceable_lines": unsupported_lines(session),
        "semantic_invented_requirements": None,
        "clarity": clarity_metrics(session),
        "calls": len(session.usage),
        "estimated_usd": sum(item.estimated_usd for item in session.usage),
        "questions": [q.model_dump() for q in questions],
        "ledger": [item.model_dump() for item in session.ledger],
        "brief": session.brief.model_dump() if session.brief else None,
        "usage": [item.model_dump() for item in session.usage],
    }


async def run(demo, output, clarity_version=1):
    settings = Settings(mode="demo" if demo else "live")
    if not demo and not (settings.nebius_api_key and settings.nebius_api_key.get_secret_value()):
        raise SystemExit("Live evaluation needs NEBIUS_API_KEY. --demo checks plumbing only.")
    models = DemoModels() if demo else LiveModels(settings)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="prompt-caller-eval-") as folder:
            store = Store(str(Path(folder) / "eval.sqlite3"))
            for strategy in ["lenses", "single"]:
                for fixture in load_fixtures():
                    result = await run_case(fixture, settings, models, store, strategy, clarity_version)
                    results.append(result)
                    print(
                        f"{strategy:6} {fixture['id']:20} ready={result['ready']} "
                        f"questions={result['questions_to_ready']} calls={result['calls']} "
                        f"cost=${result['estimated_usd']:.4f}"
                    )
    finally:
        await models.close()
    report = {
        "mode": settings.mode,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "notice": "DEMO: pipeline smoke test only; scores do not measure Nemotron quality."
        if demo
        else "Keyword hits are only a screening proxy. Manually score each planted ambiguity "
        "and semantic invented requirement using the saved questions, ledger and brief.",
        "clarity_version": clarity_version,
        "comparison": "Same extractor, ranker, slot fallback, compiler and verifier for both strategies. "
        "Six critics (up to 18 candidates/turn) vs one general critic (up to 3/turn). "
        "Model-call and candidate budgets differ; report cost alongside quality.",
        "results": results,
    }
    if clarity_version == 2:
        report["notice"] += " Read-backs were confirmed by a simulated user."
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    ready_counts = sum(result["ready"] and not result["error"] for result in results)
    turns = [result["questions_to_ready"] for result in results if result["questions_to_ready"] is not None]
    print(
        f"\n{report['notice']}\nPipeline completions: {ready_counts}/{len(results)}. "
        f"Mean questions: {statistics.mean(turns) if turns else 'n/a'}.\nSaved {path.resolve()}"
    )
    if any(result["error"] or not result["ready"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare six lenses with a single general critic.")
    parser.add_argument("--demo", action="store_true", help="Test plumbing only; makes no API calls.")
    parser.add_argument("--output", default=".data/evals/latest.json")
    parser.add_argument("--clarity-version", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    asyncio.run(run(args.demo, args.output, args.clarity_version))
