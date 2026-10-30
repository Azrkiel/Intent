# Intent

**Build what you mean.** Intent turns a rough software idea into a brief a coding agent
can build from, without guessing. It listens to the idea, keeps an explicit **Intent
Ledger** of what you actually said, asks one build-changing question at a time, plays
back its understanding for approval, and compiles a brief in which every requirement
cites the exact words it came from.

Built for the **Nebius × NVIDIA hackathon**: every reasoning pass runs on **NVIDIA
Nemotron** open models served by **Nebius Token Factory**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Node.js 22+](https://img.shields.io/badge/node-22%2B-green)
![Models: NVIDIA Nemotron](https://img.shields.io/badge/models-NVIDIA%20Nemotron-76B900)
![Inference: Nebius Token Factory](https://img.shields.io/badge/inference-Nebius%20Token%20Factory-0A0A0A)

> Working name in code: `prompt-caller`. The app, demo and homepage are called Intent.

## Demo

[![Intent: Build what you mean](docs/demo/poster.jpg)](docs/demo/README.md)

[Watch the 2:20 demo](docs/demo/README.md) (silent and music versions). At **1:28** it
shows the Token Factory endpoint and Nemotron routing; at **1:40** a recorded live
Nano + Super clarification turn; at **1:52** the redacted API evidence (eight Nano and
six Super HTTP 200 responses, including validation repairs). Scripted and prebuilt
sections of the video are labeled as such.

## The problem

Coding agents are fast, but they build what you *typed*, not what you *meant*. A
one-line prompt like "a habit tracker that syncs automatically" hides a dozen decisions
(sync how? which devices? what counts as "automatic"?) that the agent silently guesses.
Intent finds the decisions that would change the build, asks about the ones that
matter most, and hands the agent a brief where nothing is invented.

## What it does

- **Conversation → ledger.** Text or push-to-talk input is extracted into typed ledger
  entries. An entry is *confirmed* only if it carries an exact quote from your turn;
  anything the model inferred stays *unconfirmed*.
- **Six critics, one question.** Six concurrent critic lenses (data, access, behaviour,
  contradictions, edge cases, done-ness) propose questions. A ranker scores each one by
  divergence × uncertainty × cost-to-change, and Intent asks only the top question,
  with 2–3 concrete options.
- **Clarity v2 "North Star".** Six fields (who and when, the job, ambition, today, what
  good looks like, what fails it) must each pass a lexicon check, a rubric judge, your
  read-back confirmation and a two-reader agreement test (Krippendorff's α ≥ 0.80).
- **Playback and approval gate.** The build gate opens only when goal, core flow, data,
  access, non-goals and success criteria are confirmed with no conflicts. You approve a
  playback; any new utterance invalidates approval and the compiled brief.
- **Cited brief.** A large-model compiler writes the brief, a verifier rejects lines
  that are not supported by the ledger, and structural checks keep every confirmed item.
  Export it as `CLAUDE.md`.
- **Phase plans, graph and notes.** Generate a phased plan with wireframes and work
  packages, explore it as an interactive graph, discuss any section, and edit an
  Obsidian-compatible Markdown vault linked to it.
- **Agent handoff (optional).** Build a self-contained HTML app with Claude Code, or run
  plan work packages through sandboxed Codex workers with per-phase human review.

## How we used NVIDIA Nemotron

Intent splits the work into many narrow, schema-validated passes and routes each to the
smallest Nemotron model that can do it well. Routing lives in
[`backend/app/models.py`](backend/app/models.py); model IDs are set in
[`backend/app/settings.py`](backend/app/settings.py) and overridable in `.env`.

| Model (Token Factory ID) | Used for | Why this size |
| --- | --- | --- |
| **Nemotron 3 Nano 30B-A3B** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Ledger extraction, playback, Clarity v2 North Star drafting, rubric judge, readers and probes | Runs on every turn and many times per field; low latency and cost matter most |
| **Nemotron 3 Super 120B-A12B** `nvidia/nemotron-3-super-120b-a12b` | Six concurrent critics, question ranking, product-framework map and review, phase planning, brief verification, section discussion | Needs stronger reasoning across the whole ledger |
| **Nemotron 3 Ultra 550B-A55B** `nvidia/Nemotron-3-Ultra-550b-a55b` | Final brief compilation (one logical pass per session) | Highest-stakes output, run once; recompiles after a correction are deterministic |
| **Nemotron 3.5 Lightning** `nvidia/Nemotron-3_5-Lightning` | Alternate extractor compared against Nano in the live smoke test | Lets us A/B the extractor without code changes |

Design choices that make the models trustworthy here:

- **The orchestrator, not the model, owns state.** Models return validated deltas; the
  app owns ledger IDs, quote checks, impact scores and readiness. A model cannot confirm
  a requirement by quoting the assistant or an unrelated turn.
- **Structured output everywhere.** Every response is validated with Pydantic against a
  JSON schema. Invalid output gets exactly one repair retry, scoped to the failing fields
  where possible; a failed critic or extraction keeps the build gate closed.
- **Cross-tier disagreement.** In Clarity v2, the second independent reader runs on the
  other model tier, so agreement is not one model agreeing with itself.
- **Optional reasoning controls.** With `SEND_THINKING_CONTROLS=true`, Nano runs with
  thinking off, Super with a 2048-token reasoning budget and Ultra with a larger one,
  via `chat_template_kwargs.enable_thinking` and `reasoning_budget`. It is off by
  default until verified on your account.

## How Nebius Token Factory accelerated our workflow

- **One OpenAI-compatible endpoint for every model.** The backend uses the standard
  `openai` Python SDK pointed at `https://api.tokenfactory.nebius.com/v1/`. Nano, Super,
  Ultra and Lightning sit behind one key and one client, so a model change is a
  one-line `.env` edit, not a new integration.
- **Right-sizing per pass.** Because three Nemotron sizes are available side by side, we
  could put the frequent passes on Nano and save Super and Ultra for the passes that need
  them. The six critics run concurrently against Super.
- **Fast iteration from the catalog.** The [model catalog](https://tokenfactory.nebius.com/model-catalog.md)
  let us add Lightning as a live A/B extractor in the smoke test
  ([`backend/smoke.py`](backend/smoke.py)) and compare it with Nano on the same probe.
- **JSON-mode structured output** ([docs](https://docs.tokenfactory.nebius.com/ai-models-inference/json))
  matches our validate-and-repair contract, so schema errors surface as repairable
  responses rather than crashes.
- **Usage data for budgets.** Token counts from each response feed per-session cost
  estimates and a hard budget (`SESSION_BUDGET_USD`, default $2). Concurrent calls
  reserve their maximum estimated cost first. Recorded live usage for a full
  clarification, compile and eight planning attempts was about **$0.16 across 75
  responses** (estimates from published prices, not invoices).
- **Honest failures.** Token Factory errors such as HTTP 529 overload are surfaced and
  recorded, never replaced by scripted output. There is no fallback from live to demo.

### Other Nebius tools or services

Nebius **Token Factory** is the only Nebius service Intent uses: inference for all NVIDIA
Nemotron models, the model catalog and the structured-output API. The app runs locally
and does not use other Nebius compute, storage or managed services.

## Architecture

```text
Voice or text
    |
    v
Nano extraction --> exact source-quote checks --> SQLite ledger
                                                   |
                                                   v
             Data / Access / Behaviour / Contradictions / Edges / Done-ness   (Super x6)
                                                   |
                                                   v
           Super ranker --> divergence x uncertainty x cost to change
                                                   |
                                           one useful question
                                                   |
                                   answer --> extraction loop
                                                   |
                           ready --> playback --> explicit approval
                                                   |
                        Ultra brief --> Super verifier --> structural checks
                                                   |
                                cited CLAUDE.md --> phase plan / coding adapter
```

| Layer | Stack |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Web Speech API |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLite, streamed server-sent events |
| Models | NVIDIA Nemotron 3 Nano / Super / Ultra via Nebius Token Factory (`openai` SDK) |
| Agent adapters (optional) | Claude Code CLI (HTML builds), Codex app-server (phase work packages) |

## Setup

### Prerequisites

- [Node.js](https://nodejs.org/) 22+
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Git
- For live mode: a [Nebius Token Factory](https://tokenfactory.nebius.com/) API key
- Optional, for builds: the [Claude Code CLI](https://code.claude.com/docs/en/overview), installed and signed in

### 1. Install

```bash
git clone https://github.com/Azrkiel/Intent.git
```

```bash
cd Intent
```

```bash
uv sync --group dev
```

```bash
npm ci
```

### 2. Run in demo mode (no API key needed)

```bash
npm run dev
```

Open **http://127.0.0.1:3000** and choose **Workspace**. The API runs on port 8000 with
interactive docs at http://127.0.0.1:8000/docs. Both bind to loopback; press Ctrl+C to
stop. Demo mode is **scripted**: it makes no model calls, and every simulated pass and
the prebuilt preview are labeled.

Try the habit-tracker example: pick a sync mechanism, clarify "automatic", define the
core flow and exclusions, and choose an observable success criterion. When the meter
reaches 100%, approve the playback, compile the brief, and compare the raw transcript
with the cited requirements.

### 3. Connect NVIDIA Nemotron on Token Factory (live mode)

Copy the example environment file:

```bash
cp .env.example .env
```

Then set these two values in `.env`:

```dotenv
PROMPT_CALLER_MODE=live
NEBIUS_API_KEY=your-token-factory-key
```

Restart `npm run dev` and start a **new** conversation (sessions keep the mode they were
created with). The key stays on the server; the browser never receives it. Live mode
sends the current utterance, ledger and question history to Token Factory.

Check your key and model access before a demo:

```bash
uv run python -m backend.smoke --output .data/live-check/basic.json
```

This runs Nano and Lightning extraction plus a Super critic and writes a redacted report
(tokens, latency and estimated cost; no keys or raw responses) under the ignored `.data/`
directory. A missing key fails without making requests.

### 4. Optional: build with Claude Code

After approving and compiling a brief, set `ALLOW_CLAUDE_BUILD=true` in `.env` and
restart. **Build with Claude Code** writes the approved `CLAUDE.md` into
`.data/builds/<session>/`, runs the CLI with restricted file tools, a dollar budget and a
timeout, and shows the resulting `index.html` in a sandboxed preview. The Token Factory
key is never passed to the agent.

Codex phase execution is also available behind `ALLOW_CODEX_EXECUTION=true`; see the
[engineering log](docs/engineering-log.md#codex-execution-and-phase-staging-api).

### Troubleshooting

- **Certificate errors on managed machines:** use `uv --system-certs sync --group dev`,
  and point npm at your organization's CA bundle with `NODE_EXTRA_CA_CERTS`. Keep TLS
  verification on.
- **Second local instance:** run the API with `FRONTEND_PORT` and `DATABASE_PATH` set,
  and Next.js with `INTENT_API_PORT`; details in the
  [engineering log](docs/engineering-log.md#editable-markdown-vault-and-graph).
- **All configuration** (model IDs, budgets, timeouts, adapters) is documented in
  [`.env.example`](.env.example).

## Testing and evaluation

```bash
uv run pytest -q
```

```bash
uv run ruff check backend
```

```bash
npm test
```

```bash
npm run typecheck
```

```bash
npm run build
```

```bash
npm run eval:demo
```

`npm run eval:demo` runs 16 scripted pipeline evaluations with no API credits; it checks
plumbing, not model quality. `uv run python -m backend.evals.run` runs the same eight
annotated ambiguity fixtures live against Token Factory (uses credits) and compares the
six-lens critics with a single general critic. Browser tests: `npm run test:e2e` (stop
the dev server first; they share `frontend/.next`).

The backend suite has 500+ tests covering quote checks, the build gate, retries and JSON
repair, persistence, the API, a simulated-HTTP run of the real Token Factory adapter, and
agent-process isolation. None of them call a provider.

## Status and honest limits

- **Live-verified:** Token Factory authentication and model inventory; Nano, Lightning and
  Super smoke tests; a full live clarification session; Ultra brief compilation with Super
  verification returning no rejected items; the recorded demo turn.
- **Not yet live-qualified:** live Nemotron phase planning has not produced a complete,
  approved plan (eight audited attempts: seven stopped at strict validation checks, one at a
  provider overload; see the
  [retrospective](docs/retrospectives/2026-10-29-seven-planning-attempts.md)). Clarity v2
  has no live qualification run yet. No paid coding-agent build is claimed.
- **Generated apps are self-contained HTML.** The Claude Code adapter does not build a
  backend or implement cross-device sync, and is told to say so rather than simulate it.
- **Local, single user.** No accounts or authentication; keep it on loopback. Session data
  is stored unencrypted in the ignored `.data/` directory.

## Project map

```text
frontend/app/            Homepage and workspace (conversation, ledger, brief, graph, build)
frontend/components/     Plan graph, Markdown vault, execution and clarity panels
frontend/lib/            Typed API/SSE client and browser speech
backend/app/models.py    Token Factory adapter: Nemotron routing, JSON repair, usage
backend/app/engine.py    Extract -> six critics -> rank -> ask -> playback -> compile
backend/app/domain.py    Ledger contracts, quote checks, ranking, gate, traceability
backend/app/clarity/     Clarity v2: North Star fields, decisions, scenarios, canary review
backend/app/planning/    Phase planning, constrained repair and plan bundles
backend/app/codex/       Codex app-server client and worker sandbox
backend/app/builder.py   Restricted Claude Code subprocess and HTML preview
backend/app/main.py      FastAPI routes and streamed turn events
backend/evals/           Annotated ambiguity fixtures and comparison runner
backend/tests/           Offline test suite
docs/                    Demo, specs, plans, retrospectives and engineering log
```

## Further reading

- [Engineering log](docs/engineering-log.md): full feature reference, API routes, operator
  commands and the dated verification record.
- [Specs](docs/specs/) and [plans](docs/plans/) for each feature.
- [Token Factory text generation](https://docs.tokenfactory.nebius.com/api-reference/examples/text-generation),
  [structured output](https://docs.tokenfactory.nebius.com/ai-models-inference/json) and
  [model catalog](https://tokenfactory.nebius.com/model-catalog.md).

## License

Intent is released under the [MIT License](LICENSE), an
[OSI-approved](https://opensource.org/license/mit) open-source license.
Copyright (c) 2026 Kevin Jiang.

NVIDIA Nemotron models are used through Nebius Token Factory under their own model
licenses; this repository does not redistribute model weights.
