import argparse
import asyncio
import json

from backend.app import prompts
from backend.app.domain import Critique, Delta, Session, Turn, apply_delta
from backend.app.models import LiveModels, ModelError
from backend.app.settings import Settings
from backend.smoke_report import write_report


async def run(thinking_controls: bool, output=".data/live-check/basic.json", provider_factory=LiveModels):
    settings = Settings(mode="live", send_thinking_controls=thinking_controls)
    records = []
    key = settings.nebius_api_key
    if not key or not key.get_secret_value():
        write_report(
            output,
            [{"model": "configuration", "passed": False, "failure": "missing_credentials", "usage": []}],
            thinking_controls,
        )
        print("Set NEBIUS_API_KEY in .env before running the live check.")
        raise SystemExit(1)
    text = (
        "I want a habit tracker, no login, saved across my phone and laptop, "
        "and reminders should be automatic."
    )
    for model in [settings.nano_model, "nvidia/Nemotron-3_5-Lightning"]:
        session = Session(mode="live", turns=[Turn(number=1, text=text)])
        provider = provider_factory(settings.model_copy(update={"nano_model": model}))
        result = {"model": model, "passed": False, "grounded_items": 0, "failure": None, "usage": []}
        try:
            delta = await provider.call(
                session, "extractor", Delta, prompts.EXTRACT, {"text": text, "ledger": [], "turn": 1}
            )
            apply_delta(session, delta, 1)
            result["grounded_items"] = sum(item.status == "confirmed" for item in session.ledger)
            if not result["grounded_items"]:
                raise ModelError("Extraction produced no grounded requirements")
            if model == settings.nano_model:
                critique = await provider.call(
                    session,
                    "critic:contradictions",
                    Critique,
                    prompts.critic_prompt("contradictions"),
                    {"ledger": [item.model_dump() for item in session.ledger], "already_asked": []},
                )
                ids = {item.id for item in session.ledger}
                useful = [
                    question
                    for question in critique.candidates
                    if question.lens == "contradictions"
                    and question.targets
                    and set(question.targets) <= ids
                    and question.divergence > 1
                ]
                if not useful:
                    raise ModelError("No useful contradiction question for the planted gap")
            result["passed"] = True
        except (ModelError, ValueError) as error:
            result["failure"] = "model_error" if isinstance(error, ModelError) else "ledger_validation"
        finally:
            result["usage"] = [item.model_dump() for item in session.usage]
            records.append(result)
            await provider.close()
    report = write_report(output, records, thinking_controls)
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Nano/Lightning extraction and Super JSON smoke test.")
    parser.add_argument("--thinking-controls", action="store_true")
    parser.add_argument("--output", default=".data/live-check/basic.json")
    args = parser.parse_args()
    asyncio.run(run(args.thinking_controls, args.output))
