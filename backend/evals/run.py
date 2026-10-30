import argparse
import asyncio
import json
import re
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.app.clarity.metrics import clarity_metrics
from backend.app.clarity.northstar import KEEP, OWN
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


STOP = {"and", "the", "for", "with", "that", "this", "are", "not", "but", "can", "will", "all", "any"}


def words(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.casefold())) - STOP


def pick_option(question, fixture):
    """Simulated user picks the offered draft/option closest to the fixture's answers (token overlap)."""
    options = [o for o in question.options if o.strip() not in (KEEP, OWN)] or question.options
    gaps = [g["answer"] + " " + " ".join(g["keywords"]) for g in fixture["ambiguities"]]
    target = words(" ".join([fixture["prompt"], *gaps]))
    best = max(options, key=lambda option: len(words(option) & target))
    # Under three shared words is noise; fall back to the first option (the model's best guess).
    return best if len(words(best) & target) >= 3 else options[0]


def answer_for(question, fixture, clarity_version=1):
    if clarity_version == 2 and (question.suggestion or question.lens == "decision"):
        return pick_option(question, fixture)
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
    if isinstance(models, LiveModels):
        models.capture_raw = True  # keep unparseable output for the report; never reaches the API
    session = Session(mode=settings.mode, clarity_version=clarity_version)
    store.save(session)
    engine = Engine(store, models, critic_mode=strategy)
    text = fixture["prompt"]
    error = None
    rounds = []
    for _ in range(13):
        async for event in engine.turn(session, text):
            if event["type"] == "error":
                error = event["message"]
        if session.clarity_version == 2 and session.clarity:
            # Simulated user: confirms every read-back that is the only failing check.
            for field in list(session.clarity.fields):
                if field.failing == ["G3"]:
                    await engine.confirm_readback(session, field.field, field.text_hash)
            # Per-round North Star state: convergence cannot be diagnosed from the final state alone.
            rounds.append({
                "answer": text,
                "fields": {
                    f.field: {
                        "text": f.text,
                        "failing": f.failing,
                        "reasons": {
                            v.rule: v.reason
                            for v in (f.judgement.verdicts if f.judgement else [])
                            if not v.passed
                        },
                    }
                    for f in session.clarity.fields
                },
            })
        if error or session.warnings:
            error = error or "; ".join(session.warnings)
            break
        if gate_for(session).ready or not session.current_question:
            break
        text = answer_for(session.current_question, fixture, clarity_version)
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
        "raw_failures": getattr(models, "raw_failures", {}).get(session.id, []),
        "rounds": rounds,
        "calls": len(session.usage),
        "estimated_usd": sum(item.estimated_usd for item in session.usage),
        "questions": [q.model_dump() for q in questions],
        "ledger": [item.model_dump() for item in session.ledger],
        "brief": session.brief.model_dump() if session.brief else None,
        "usage": [item.model_dump() for item in session.usage],
    }


async def run(demo, output, clarity_version=1, max_total_usd=None, fixture_ids=None, strategies=None):
    settings = Settings(mode="demo" if demo else "live")
    if not demo and not (settings.nebius_api_key and settings.nebius_api_key.get_secret_value()):
        raise SystemExit("Live evaluation needs NEBIUS_API_KEY. --demo checks plumbing only.")
    models = DemoModels() if demo else LiveModels(settings)
    results = []
    stopped = None
    session_cap = settings.session_budget_usd
    fixtures = [f for f in load_fixtures() if not fixture_ids or f["id"] in fixture_ids]
    try:
        with tempfile.TemporaryDirectory(prefix="prompt-caller-eval-") as folder:
            store = Store(str(Path(folder) / "eval.sqlite3"))
            for strategy in strategies or ["lenses", "single"]:
                for fixture in fixtures:
                    if max_total_usd is not None:
                        # Hard cap: each session may spend only what the whole run has left.
                        remaining = max_total_usd - sum(r["estimated_usd"] for r in results)
                        if remaining < 0.05:
                            stopped = f"Stopped before {strategy}/{fixture['id']}: ${max_total_usd} cap."
                            break
                        settings.session_budget_usd = min(session_cap, remaining)
                    result = await run_case(fixture, settings, models, store, strategy, clarity_version)
                    results.append(result)
                    print(
                        f"{strategy:6} {fixture['id']:20} ready={result['ready']} "
                        f"questions={result['questions_to_ready']} calls={result['calls']} "
                        f"cost=${result['estimated_usd']:.4f}"
                    )
                if stopped:
                    break
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
        "max_total_usd": max_total_usd,
        "estimated_total_usd": sum(r["estimated_usd"] for r in results),
        "stopped": stopped,
        "comparison": "Same extractor, ranker, slot fallback, compiler and verifier for both strategies. "
        "Six critics (up to 18 candidates/turn) vs one general critic (up to 3/turn). "
        "Model-call and candidate budgets differ; report cost alongside quality.",
        "results": results,
    }
    if clarity_version == 2:
        report["notice"] += (
            " Read-backs were confirmed, and drafts/options were picked, by a simulated user."
        )
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    ready_counts = sum(result["ready"] and not result["error"] for result in results)
    turns = [result["questions_to_ready"] for result in results if result["questions_to_ready"] is not None]
    print(
        f"\n{report['notice']}\nPipeline completions: {ready_counts}/{len(results)}. "
        f"Mean questions: {statistics.mean(turns) if turns else 'n/a'}. "
        f"Estimated cost: ${report['estimated_total_usd']:.4f}.\nSaved {path.resolve()}"
    )
    if stopped:
        print(stopped)
    if stopped or any(result["error"] or not result["ready"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare six lenses with a single general critic.")
    parser.add_argument("--demo", action="store_true", help="Test plumbing only; makes no API calls.")
    parser.add_argument("--output", default=".data/evals/latest.json")
    parser.add_argument("--clarity-version", type=int, choices=[1, 2], default=1)
    parser.add_argument("--max-total-usd", type=float, help="Stop the run at this estimated total spend.")
    parser.add_argument("--fixture", action="append", dest="fixtures", help="Fixture id; repeatable.")
    parser.add_argument("--strategy", action="append", dest="strategies", choices=["lenses", "single"])
    args = parser.parse_args()
    asyncio.run(run(
        args.demo, args.output, args.clarity_version, args.max_total_usd, args.fixtures, args.strategies
    ))
