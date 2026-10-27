import argparse
import asyncio
import json

from backend.app import prompts
from backend.app.domain import Critique, Delta, Session, Turn, apply_delta
from backend.app.models import LiveModels, ModelError
from backend.app.settings import Settings


async def run(thinking_controls: bool):
    settings = Settings(mode="live", send_thinking_controls=thinking_controls)
    text = (
        "I want a habit tracker, no login, saved across my phone and laptop, "
        "and reminders should be automatic."
    )
    if not settings.nebius_api_key or not settings.nebius_api_key.get_secret_value():
        raise SystemExit("Set NEBIUS_API_KEY in .env before running the live smoke test.")
    passed = True
    for model in [settings.nano_model, "nvidia/Nemotron-3_5-Lightning"]:
        session = Session(mode="live", turns=[Turn(number=1, text=text)])
        provider = LiveModels(settings.model_copy(update={"nano_model": model}))
        try:
            delta = await provider.call(
                session, "extractor", Delta, prompts.EXTRACT, {"text": text, "ledger": [], "turn": 1}
            )
            apply_delta(session, delta, 1)
            if model == settings.nano_model:
                await provider.call(
                    session,
                    "critic:contradictions",
                    Critique,
                    prompts.critic_prompt("contradictions"),
                    {"ledger": [item.model_dump() for item in session.ledger], "already_asked": []},
                )
            print(
                json.dumps(
                    {
                        "model": model,
                        "valid_json": True,
                        "confirmed_items": sum(item.status == "confirmed" for item in session.ledger),
                        "usage": [item.model_dump() for item in session.usage],
                    },
                    indent=2,
                )
            )
        except ModelError as error:
            passed = False
            print(json.dumps({"model": model, "valid_json": False, "error": str(error)}))
        finally:
            await provider.close()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Nano/Lightning extraction and Super JSON smoke test.")
    parser.add_argument("--thinking-controls", action="store_true")
    asyncio.run(run(parser.parse_args().thinking_controls))
