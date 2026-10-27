# Next milestone: qualify the live Nemotron path

**Goal:** make the existing live smoke check produce a repeatable, redacted result,
then prove one real clarification-to-brief session before expanding generated apps.

**Architecture:** keep `LiveModels` as the sole provider adapter and keep readiness
in the orchestrator. Extract smoke-report writing into a small pure module, preserve
usage on failed probes, and run the existing Nano/Super/Lightning checks with and
without requested thinking controls. The final qualification uses the real browser
flow, including Ultra compilation and Super verification.

**Stack:** existing Python, Pydantic, OpenAI SDK, pytest, FastAPI and Next.js.
No new dependencies, services, accounts or deployment.

**Progress (2026-10-26, America/New_York):** checkpoints 1–3 are implemented
and committed as `2867a4f`, `3ecbabd` and `1ed2f87`. Verification: 45 backend
tests, Ruff, 3 frontend tests, TypeScript checking and all 16 scripted demo
pipeline runs passed. The new runner also rejects empty critic targets and omits
raw exceptions from CLI output. Both smoke configurations were attempted; each
wrote an ignored `missing_credentials` report and exited 1 without requests.
Checkpoint 4 remains pending until `NEBIUS_API_KEY` is configured locally and
actual model/browser evidence exists. No production build was run during this
milestone because a dev server was active and frontend code was unchanged.

**Starting point:** `c49e2ca` implements the first slice; `fbff0f3` records frequent
verified commits. Baseline: 29 backend tests, 3 frontend stream tests and a successful
production build. Those results validate implementation, not live model quality.

## Flow and failure paths

```text
[Run smoke CLI]
       |
       +-- no API key --> [Redacted failed report; exit 1; zero requests]
       |
       v
[Nano extraction] ---- invalid JSON --> [One repair retry]
       |                                      |
       |                                  still invalid
       |                                      |
       +-- no grounded evidence --------------+--> [Record failure + usage]
       |
       v
[Super contradiction critic]
       |
       +-- no useful question / bad targets ------> [Record failure + usage]
       |
       v
[Lightning extraction; same input]
       |
       +-- request failure -----------------------> [Record failure + usage]
       |
       v
[Write report; exit 0 only if every probe passed]
       |
       v
[Repeat with requested thinking controls]
       |
       +-- rejected / no observed benefit --> [Keep compatibility defaults]
       |
       v
[Real browser interview --> playback --> approve --> Ultra --> Super verifier]
       |
       +-- drift / missing decision --> [Regression test; prompt or contract fix]
       |
       v
[Save cited brief + measured latency/cost; commit verified fixes]
```

Reports record **requested** thinking controls. A successful HTTP response does not
prove the provider honored a thinking budget. Do not label controls as verified
without evidence from provider documentation or response metadata.

## File map

| File                                       | Responsibility                                                           |
| ------------------------------------------ | ------------------------------------------------------------------------ |
| `backend/smoke_report.py` (new)            | Whitelist report fields, retain per-call usage, save one JSON object.    |
| `backend/tests/test_smoke_report.py` (new) | Report contents, redaction and empty-result failure.                     |
| `backend/smoke.py`                         | Collect probe results, save partial failures, accept an output path.     |
| `backend/tests/test_smoke.py` (new)        | No-key/no-request behavior and billed failures using injected providers. |
| `backend/tests/test_models.py`             | Check the outgoing thinking-control fields against mock HTTP requests.   |
| `README.md`                                | Document saved reports and actual qualification results.                 |
| `.data/live-check/` (ignored)              | Local reports, audited brief and live session export.                    |

## Checkpoint 1: redacted report helper

- [x] Add `backend/tests/test_smoke_report.py`:

```python
import json

from backend.smoke_report import write_report


def test_empty_report_is_not_a_success(tmp_path):
    output = tmp_path / "empty.json"
    assert not write_report(output, [], False)["passed"]
    assert json.loads(output.read_text())["mode"] == "live"


def test_report_keeps_usage_but_drops_unapproved_fields(tmp_path):
    output = tmp_path / "nested" / "basic.json"
    usage = dict(role="extractor", model="nano", input_tokens=20,
                 output_tokens=10, estimated_usd=0.000004, latency_ms=100)
    record = dict(model="nano", passed=False, failure="model_error",
                  grounded_items=0, usage=[usage], api_key="test-secret",
                  raw_response="test-secret", error="test-secret")
    report = write_report(output, [record], True)
    assert not report["passed"]
    assert report["thinking_controls_requested"] is True
    assert report["results"][0]["usage"] == [usage]
    assert "test-secret" not in output.read_text()
```

- [x] Run `uv run pytest backend/tests/test_smoke_report.py -q`.
      Expected RED: `ModuleNotFoundError: No module named 'backend.smoke_report'`.
- [x] Add `backend/smoke_report.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.domain import Usage


def write_report(output, records, thinking_controls):
    allowed_failures = {"missing_credentials", "model_error", "ledger_validation"}
    results = []
    for record in records:
        failure = record.get("failure")
        results.append({
            "model": record["model"],
            "passed": bool(record["passed"]),
            "grounded_items": int(record.get("grounded_items", 0)),
            "failure": failure if failure in allowed_failures else None,
            "usage": [Usage.model_validate(item).model_dump()
                      for item in record.get("usage", [])],
        })
    report = {
        "mode": "live",
        "scope": "protocol_smoke_not_quality_evaluation",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "thinking_controls_requested": bool(thinking_controls),
        "passed": bool(results) and all(item["passed"] for item in results),
        "results": results,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
```

- [x] Run the targeted tests, then `uv run ruff check backend`.
      Expected: 2 passing new tests and no Ruff findings. Format imports with
      `uv run ruff check backend --select I --fix` and `uv run ruff format backend`
      before the check if needed.
- [x] Commit: `git add backend/smoke_report.py backend/tests/test_smoke_report.py`
      then `git commit -m "feat: add redacted live model smoke reports"`.

## Checkpoint 2: preserve failed probe costs and validate actual gaps

- [x] Add `backend/tests/test_smoke.py` with these two regression tests:

```python
import json

import pytest
from pydantic import SecretStr

from backend import smoke
from backend.app.domain import Usage
from backend.app.models import ModelError
from backend.app.settings import Settings


async def test_missing_key_writes_failure_without_creating_a_provider(tmp_path, monkeypatch):
    config = Settings(_env_file=None, NEBIUS_API_KEY=None)
    monkeypatch.setattr(smoke, "Settings", lambda **kwargs: config)

    def forbidden_factory(settings):
        pytest.fail("A missing key must make zero requests")

    output = tmp_path / "missing.json"
    with pytest.raises(SystemExit) as error:
        await smoke.run(False, output, provider_factory=forbidden_factory)
    assert error.value.code == 1
    report = json.loads(output.read_text())
    assert report["results"][0]["failure"] == "missing_credentials"
    assert report["results"][0]["usage"] == []


async def test_failed_probes_preserve_usage_and_close_clients(tmp_path, monkeypatch):
    config = Settings(_env_file=None, NEBIUS_API_KEY=SecretStr("test-only"))
    monkeypatch.setattr(smoke, "Settings", lambda **kwargs: config)
    closed = []

    class FailingProvider:
        def __init__(self, settings):
            self.model = settings.nano_model

        async def call(self, session, role, schema, instruction, payload):
            session.usage.append(Usage(role=role, model=self.model,
                input_tokens=20, output_tokens=10, estimated_usd=0.000004,
                latency_ms=100))
            raise ModelError("Invalid JSON after repair")

        async def close(self):
            closed.append(self.model)

    output = tmp_path / "failed.json"
    with pytest.raises(SystemExit) as error:
        await smoke.run(False, output, provider_factory=FailingProvider)
    assert error.value.code == 1
    report = json.loads(output.read_text())
    assert len(closed) == 2
    assert len(report["results"]) == 2
    assert sum(len(item["usage"]) for item in report["results"]) == 2
    assert not report["passed"]
    assert "test-only" not in output.read_text()
```

- [x] Run `uv run pytest backend/tests/test_smoke.py -q`.
      Expected RED: the existing `run` does not accept `provider_factory` or an output path.
- [x] Import `write_report` into `backend/smoke.py`, then replace its `run` function
      with this implementation. Retain the existing domain/model/settings imports.

```python
async def run(thinking_controls, output=".data/live-check/basic.json",
              provider_factory=LiveModels):
    settings = Settings(mode="live", send_thinking_controls=thinking_controls)
    records = []
    key = settings.nebius_api_key
    if not key or not key.get_secret_value():
        write_report(output, [{"model": "configuration", "passed": False,
            "failure": "missing_credentials", "usage": []}], thinking_controls)
        print("Set NEBIUS_API_KEY in .env before running the live check.")
        raise SystemExit(1)

    text = ("I want a habit tracker, no login, saved across my phone and laptop, "
            "and reminders should be automatic.")
    for model in [settings.nano_model, "nvidia/Nemotron-3_5-Lightning"]:
        session = Session(mode="live", turns=[Turn(number=1, text=text)])
        provider = provider_factory(settings.model_copy(update={"nano_model": model}))
        result = {"model": model, "passed": False, "grounded_items": 0,
                  "failure": None, "usage": []}
        try:
            delta = await provider.call(session, "extractor", Delta, prompts.EXTRACT,
                {"text": text, "ledger": [], "turn": 1})
            apply_delta(session, delta, 1)
            result["grounded_items"] = sum(
                item.status == "confirmed" for item in session.ledger)
            if not result["grounded_items"]:
                raise ModelError("Extraction produced no grounded requirements")
            if model == settings.nano_model:
                critique = await provider.call(session, "critic:contradictions", Critique,
                    prompts.critic_prompt("contradictions"),
                    {"ledger": [item.model_dump() for item in session.ledger],
                     "already_asked": []})
                ids = {item.id for item in session.ledger}
                useful = [q for q in critique.candidates
                    if q.lens == "contradictions" and set(q.targets) <= ids
                    and q.divergence > 1]
                if not useful:
                    raise ModelError("No useful contradiction question for the planted gap")
            result["passed"] = True
        except (ModelError, ValueError) as error:
            result["failure"] = "model_error" if isinstance(error, ModelError) else "ledger_validation"
            print(f"{model}: {error}")
        finally:
            result["usage"] = [item.model_dump() for item in session.usage]
            records.append(result)
            await provider.close()
    report = write_report(output, records, thinking_controls)
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)
```

- [x] Add `parser.add_argument("--output", default=".data/live-check/basic.json")`
      to the existing CLI parser. Replace the final invocation with:

```python
args = parser.parse_args()
asyncio.run(run(args.thinking_controls, args.output))
```

- [x] Run `uv run pytest backend/tests/test_smoke.py backend/tests/test_smoke_report.py -q`,
      `uv run pytest -q`, and `uv run ruff check backend`.
      Expected: the four new tests pass; the existing 29 backend tests remain green.
- [x] Commit only the smoke runner and its new tests:
      `git add backend/smoke.py backend/tests/test_smoke.py`, then
      `git commit -m "fix: retain failed live probe usage and require grounded outputs"`.

## Checkpoint 3: outgoing thinking-control contracts

- [x] Add this test to `backend/tests/test_models.py`. It reuses the existing
      `completion` helper and existing imports.

```python
@pytest.mark.parametrize("role,enabled,budget", [
    ("extractor", False, None),
    ("critic:contradictions", True, 2048),
    ("compiler", True, 6144),
])
async def test_requested_thinking_controls_are_sent(role, enabled, budget):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"add": []}'))

    client = AsyncOpenAI(api_key="test", base_url="https://test.invalid/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    provider = LiveModels(Settings(send_thinking_controls=True), client=client)
    try:
        await provider.call(Session(), role, Delta, "Return the test JSON contract.", {})
        body = requests[0]
        assert body["chat_template_kwargs"] == {"enable_thinking": enabled}
        if budget is None:
            assert "reasoning_budget" not in body
        else:
            assert body["reasoning_budget"] == budget
    finally:
        await client.close()
```

This characterizes existing behavior and should pass immediately; do not manufacture
a failure by changing working code. The deliberately small `Delta` response here
tests transport fields only, not the compiler's real brief schema.

- [x] Extend the existing default-controls-off test with:

```python
assert "chat_template_kwargs" not in requests[0]
assert "reasoning_budget" not in requests[0]
```

- [x] Run `uv run pytest backend/tests/test_models.py -q` and `uv run ruff check backend`.
      Expected: 6 model tests pass, no network calls, no secrets in output.
- [x] Commit: `git add backend/tests/test_models.py`, then
      `git commit -m "test: characterize optional Nemotron thinking controls"`.

## Checkpoint 4: actual live qualification

**Prerequisite:** `NEBIUS_API_KEY` must be configured in the ignored `.env` file.
It was absent when this plan was written. Do not request a key in chat or copy one
from an unrelated app. Offline implementation and tests can proceed without it.

- [ ] Run `uv run python -m backend.smoke --output .data/live-check/basic.json`.
      Expected: exit 0 only if Nano and Lightning extract grounded items and Super
      proposes a useful contradiction question with valid targets. Each successful
      API response, including failed JSON repairs, retains tokens, cost and latency.
- [ ] Run `uv run python -m backend.smoke --thinking-controls --output .data/live-check/controls.json`.
      Expected: either a separately saved passing report, or exit 1 with explicit
      failed probes and retained usage. Keep `SEND_THINKING_CONTROLS=false` if rejected.
      Compare extractor rows, not Nano's extraction-plus-critic total against Lightning.
- [ ] Set `PROMPT_CALLER_MODE=live` in `.env`, restart with `npm run dev`, and create
      a **new** conversation. Never change a restored demo session into a live one.
- [ ] Use the habit-tracker fixture and answer each actual question. Verify that
      the sync/access tradeoff and the meaning of automatic reminders are addressed,
      negative constraints remain intact, and corrections update existing decisions.
- [ ] Complete playback approval and compilation. Check every brief line against
      its cited source and check every confirmed decision appears. Verify the session's
      usage includes the Ultra compiler and Super verifier. One example is a live
      integration check, not a measured catch rate.
- [ ] Check blank input, one correction after approval, a failed/retried model pass,
      and session restoration. None may silently switch to demo or retain stale approval.
- [ ] Save the session export and compiled `CLAUDE.md` under `.data/live-check/`.
      Use the current session's existing export link and API detail response. Keep the
      outputs local and ignored; record only aggregate findings in the README.
- [ ] Update the README with the dated model IDs, requested controls, observed
      validity, per-pass latencies and estimated spend. If any gate fails, record that
      failure; add a focused regression test before fixing it. Do not claim a live pass
      without an actual successful run.
- [ ] Check `git diff --check` and commit the README separately:
      `git add README.md`, then `git commit -m "docs: record live Nemotron qualification results"`.

## Acceptance and sequencing

The milestone is complete when reports survive failures without leaking credentials,
offline tests pass, and one real session reaches a faithful approved brief. The live
portion remains incomplete until credentials and actual provider evidence exist.

After this milestone, implement real generated-app backend execution and test the
authenticated Claude Code handoff so the sync decision produces a different working
app. Then run the eight live fixtures, manually score ambiguity catches and invented
requirements, and record the demo. Keep accounts, deployment and extra agent adapters
out of this sequence.

Self-review: every step maps to an existing contract or a named new file; code and
commands are explicit; reports are ignored; each implementation checkpoint has a
small commit. The live qualification remains distinct from offline contract tests.
