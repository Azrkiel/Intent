# Prompt Caller

Turn a rough software idea into a brief a coding agent can build from. The application
keeps an explicit **Intent Ledger**, asks one build-changing question at a time, plays
back its understanding, and compiles a brief with a source for every requirement.

This is a local, single-user MVP. The default **demo mode is scripted**: it makes no
model calls and the build preview is a clearly labeled prebuilt example. The live
Nemotron adapter and Claude Code subprocess adapter are implemented, but need your
credentials and a live smoke test before a demo or submission.

## Run locally

Prerequisites: Node.js 22+, Python 3.11+, [uv](https://docs.astral.sh/uv/), and Git.
For live builds, install and authenticate the [Claude Code CLI](https://code.claude.com/docs/en/overview).

```powershell
uv sync --group dev
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. The orchestrator runs on port 8000; interactive API
documentation is at http://127.0.0.1:8000/docs. Both servers bind to loopback. Use
Ctrl+C to stop them. The launcher stops the processes it started, including their
child processes on Windows.

If `uv` reports an unknown certificate issuer on a managed Windows machine, use
`uv --system-certs sync --group dev`. For npm, use your organization's trusted CA
bundle with `NODE_EXTRA_CA_CERTS`; keep certificate verification enabled.

Start with the habit-tracker example. Choose a sync mechanism, clarify “automatic,”
define the core flow and exclusions, and pick an observable success criterion. Once
the meter reaches 100%, review the playback, approve it, and compile the brief.
Compare the raw transcript with the cited requirements, export `CLAUDE.md`, or try
the labeled demo handoff.

## Connect Nemotron

Copy `.env.example` to `.env` in the repository root and edit:

```dotenv
PROMPT_CALLER_MODE=live
NEBIUS_API_KEY=your-token-factory-key
```

Restart the server after changing environment variables. The browser never receives
the API key. Live mode sends the current utterance, ledger and question history to
Token Factory for model processing. Existing sessions retain their original mode; create a new conversation
after switching modes. There is no silent fallback from live mode to demo responses.

The OpenAI SDK targets `https://api.tokenfactory.nebius.com/v1/`. Routing defaults:

| Pass                               | Model                                   | Behaviour                             |
| ---------------------------------- | --------------------------------------- | ------------------------------------- |
| Extraction and playback            | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Narrow, schema-validated outputs      |
| Six critics, ranking, verification | `nvidia/nemotron-3-super-120b-a12b`     | Six concurrent lenses, then ranking   |
| Brief compilation                  | `nvidia/Nemotron-3-Ultra-550b-a55b`     | One logical compiler pass per session |

Every response is validated with Pydantic. Invalid JSON gets one repair retry. A
failed critic keeps the build gate closed; the user can retry analysis. A failed
extraction is retried before criticism, so a correction cannot be ignored when
the gate is reevaluated.

`SEND_THINKING_CONTROLS=false` is the compatibility default. Set it to `true` after
checking the account's support for `chat_template_kwargs.enable_thinking` and
`reasoning_budget`. With controls enabled, Nano uses thinking off, Super uses the
configured budget, and Ultra uses a larger budget. With controls disabled, prompt
and output-token limits apply; the provider's default thinking behaviour is
unverified. All model IDs and the API base URL can be changed in `.env`.

Usage and latency are retained per successful API response, including invalid JSON
responses. Dollar figures use the role's published price assumptions and are
**estimates**, not invoices. Concurrent calls reserve their maximum estimated cost
before starting. `SESSION_BUDGET_USD` defaults to $2. Compiler JSON repair can make
a second API request within that logical pass. Recompiling after a correction
uses a deterministic rendering of the ledger instead of another Ultra pass.

### Day-one smoke test

```powershell
uv run python -m backend.smoke --output .data/live-check/basic.json
# After the basic requests work, test optional thinking controls:
uv run python -m backend.smoke --thinking-controls --output .data/live-check/controls.json
```

This compares extraction on Nano and Lightning and makes a Super critic request.
Each extractor must produce at least one confirmed requirement backed by an exact
source quote. The Super critic must return a contradiction question with nonempty,
valid ledger targets and divergence greater than 1. These are protocol checks;
they do not establish model quality or a measured ambiguity catch rate.

Each run saves one redacted JSON report with the requested thinking-control setting,
per-probe pass/failure status, grounded-item counts and per-call tokens, latency and
estimated cost. Usage survives failed validation and JSON repair. Reports exclude
credentials, raw responses and exception text. A missing key writes a failed report
without making requests; any failed probe exits with code 1. Reports stay local in
the ignored `.data/live-check/` directory. The check does not run automatically or
use credentials from another application.

**Qualification status (2026-10-26, America/New_York):** both CLI configurations
were attempted and exited with code 1 (`missing_credentials`). No provider requests
were made: recorded usage is empty, estimated spend is $0, and provider latency and
output validity are unmeasured. The configured Nano/Super model IDs are listed above;
the alternate extractor is `nvidia/Nemotron-3_5-Lightning`. Offline HTTP contract tests
cover controls omitted by default, Nano thinking off when controls are requested,
Super's requested 2048-token budget and Ultra's requested 6144-token budget. They
verify outgoing fields only. Provider acceptance and actual thinking behaviour remain
unverified; `SEND_THINKING_CONTROLS=false` remains the compatibility default.

Live qualification remains pending: configure `NEBIUS_API_KEY` in `.env`, rerun both
commands, then complete a new live browser conversation through playback approval,
Ultra compilation and Super verification. Audit every brief line against its cited
source, verify all confirmed decisions remain, and check corrections, failure/retry
and session restoration. Save the session export and `CLAUDE.md` locally under
`.data/live-check/`. No live session or model-quality pass is claimed.

### Offline qualification

The 2026-10-26 offline follow-up passed 57 backend tests, Ruff, 4 frontend stream
tests, TypeScript checking, the production build and all 16 scripted demo pipeline
runs. A regression test reproduces CRLF delimiters split across network chunks;
the stream parser now normalizes the joined buffer so valid responses are not
reported as interrupted.

```powershell
uv run pytest backend/tests/test_offline_pipeline.py backend/tests/test_builder_process.py -q
```

These tests exercise the real `LiveModels` adapter against simulated HTTP responses,
including failed JSON repair, retained usage, Nano/Super/Ultra routing, compilation,
SQLite restoration and correction invalidation. Their token and cost values are
synthetic. Coding-adapter tests run a local scripted subprocess to check stdout and
stderr handling, successful-result and output-file requirements, timeouts,
cancellation and process cleanup. They do not invoke Claude Code or require keys.

A production-browser demo run covered blank input, the sync/access and automatic
reminder questions, explicit approval, compilation, brief export, a labeled demo
preview, reload restoration and a correction after approval. All nine confirmed
ledger entries appeared in the demo brief. The correction updated existing data
IDs and cleared approval, the compiled brief and the prior build. Demo session
exports and the brief are saved locally under `.data/offline-check/`.

Claude Code 2.1.310 is installed and its authentication status reports signed in.
No paid coding-agent build was run. Actual provider validity, semantic brief
fidelity, live latency/spend, microphone behaviour and authenticated app generation
still need separate checks. Generated apps remain self-contained HTML and do not
run a backend or synchronize across devices.

## Visual phase plans and instruction bundles

After approving the current requirements playback, open **Phase plan** (or
**Plan phases** from the compiled brief) and choose **Generate phase plan**.
Validated outline, wireframe, and phase sections appear progressively. Switch
between **Vision & wireframes** and **Engineering & work packages** to inspect
the same revision. Proposed choices and unresolved questions remain explicit.

Choose **Approve this revision**, then **Export instruction bundle**. The ZIP
contains the canonical `plan.json`, a hashed manifest, cited specification, vision,
wireframes, architecture, shared `AGENTS.md`/compatible `CLAUDE.md`, and detailed
phase and work-package packets. Approval binds the plan ID, revision, content hash,
and requirements revision. A new utterance clears approval and preserves the old
plan for inspection. Draft, failed, or stale plans cannot export.

Planning uses Super through the existing model adapter and session budget. It does
not consume another Ultra compiler pass. An attempt has an outline pass, up to
three screen passes, up to four phase passes, and one semantic verification pass;
each allows the existing single JSON repair. Defaults allow two attempts per
session, with all reservations and response usage preserved across failure,
correction, interruption, and restart. `PLANNING_MAX_ATTEMPTS` (1–2) and
`PLANNING_MAX_PASSES` (1–9) can lower these limits. Each phase holds at most two
packages and each package at most three ordered leaf tasks. Exceeding a bound
blocks the plan rather than silently dropping work.

**Phase 1 status (2026-10-27, America/New_York):** offline implementation and demo
browser verification are complete; the user accepted Phase 1 on 2026-10-27. The suite
passes 109 backend tests, Ruff, 9 frontend tests, TypeScript checking, the production
build, and 16/16 existing scripted evaluations. Additional HTTP fixtures exercise
the live model adapter without making provider requests. The browser check covered
both views, approval, export, reload, and correction invalidation.

Demo planning is a generic, labeled synthetic fixture, not a custom model-generated
implementation contract or evidence of semantic quality. Actual Nemotron planning
qualification remains pending. The Phase 1 UI exports plans; the backend API
described below adds worker execution and phase staging. The
[implementation plan](docs/plans/2026-10-26-phase-plans-codex-orchestration.md)
records scheduling in Phase 3 and the review UI in Phase 4. The existing HTML builder remains
available separately.

## Codex execution and phase staging API

Phase 2 is implemented and verified offline against synthetic app-server processes
using the installed CLI 0.164.0 schema. It adds initialization, account/model/policy
checks, streamed events, durable permission requests, interruption, owned Git
worktrees, and restart reconciliation. Phase 2 was accepted on 2026-10-27.
Individual successful turns stop at `verifying`. Phase 3 adds a scheduler that
inspects those changes and integrates them into a separate staging branch.

The API is disabled by default. Actual use requires `PROMPT_CALLER_MODE=live`,
explicit `ALLOW_CODEX_EXECUTION=true`, current requirements and plan approval,
and an existing Codex-managed ChatGPT login. Demo sessions and synthetic plans
cannot dispatch. Keep authentication in Codex; do not copy tokens into Intent or
exports. Optional `CODEX_HOME` selects an existing separately qualified profile.
`CODEX_COMMAND` selects the local executable. Project/worktree roots and worker/
approval deadlines are documented in `.env.example`.

Workers use `workspace-write`, user approval routing, disabled automatic child
agents, and restricted network access. The initial executor conservatively blocks
inherited custom providers, hooks, plugins, MCP servers, and enabled skills until
the selected profile is separately qualified. It preserves an explicit model or
the configured/default available model and never switches billing or accounts.
Observed Codex token counts are retained separately from Nemotron dollar estimates.

| Route under `/api/sessions/{id}/execution` | Behavior |
| --- | --- |
| `POST` | Exact approved plan identity plus `package_id` and optional `model`; claim one eligible package |
| `GET` | Durable runs and phases, staged evidence, usage, permissions, changed paths, and labeled worker claims |
| `POST /phases/{phase_id}/start` | Exact approved plan identity and optional `model`; explicitly start the current phase scheduler |
| `POST /{run_id}/verify` | Exact approved plan identity; inspect a completed package and stage its verified snapshot |
| `POST /{run_id}/approvals/{request_id}` | `generation` plus `accept`, `decline`, or `cancel`; reject stale/expired/replayed decisions |
| `POST /{run_id}/cancel` | Empty JSON body; stop the owned worker and preserve changes |
| `POST /{run_id}/reconcile` | Empty JSON body; inspect known IDs before reconnecting; uncertain outcomes remain blocked |

`CODEX_MAX_WORKERS` defaults to 1 and permits at most 2. It must fit
`CODEX_GLOBAL_MAX_WORKERS` (default 2, maximum 2). Transactional package claims
enforce capacity, path ownership, interface compatibility and one active phase.
Compatible readers may share an integrated interface; producers and conflicting
versions cannot. A dependent package starts from its prerequisite's integrated
staging commit. Worker completion alone never makes a dependency eligible.

The scheduler runs only the current phase and stops at `awaiting_phase_review`.
It never advances to a successor phase or updates the accepted project branch.
Phase acceptance, explicit repair attempts and execution/review UI remain Phase 4
work. Duplicate attempts and uncertain restart/integration outcomes remain blocked;
there is no automatic replacement worker. A failure or cancellation stops affected
workers and preserves their worktrees. New utterances invalidate runs and phase
evidence and clear plan approval.

Verification reads actual committed, modified, deleted, renamed, binary and
untracked files, including ignored files. Ownership violations, protected control
files, unsafe filesystem links, missing artifacts, stale bases and staging conflicts
block integration. Evidence retains artifact SHA-256 hashes, changed paths, bounded
redacted diffs, check provenance and unresolved decisions. Worker summaries and
worker-edited tests remain claims and changed code, not independent test evidence.

The initial trusted policy is **`git-inspection-only-v1`**. Its only accepted
proposed command is the exact argv `['git', 'diff', '--check']`, resolved against
the inspected base and snapshot with external diff/text conversion disabled.
Commands use a sanitized environment, a 15-second deadline and a 2 MB output bound;
inspection limits files to 2 MB each and 16 MB total. Generated tests, package
scripts, installs and arbitrary shell commands have no approved sandbox runner and
therefore block verification. Git filters/hooks/config overrides and filesystem
links in owned Git metadata are rejected. Worktrees are materialized from raw blobs
without checkout filters. Passing this policy proves scoped artifacts and Git
checks, not application correctness or semantic compliance with textual exclusions.

**Phase 2 offline evidence (2026-10-27):** 156 backend tests, Ruff, and 16/16 scripted
evaluations pass. Tests use real local subprocesses and temporary Git repositories,
including Windows descendant cleanup after parent exit, cancellation, stale
permissions, out-of-scope changes, and uncertain dispatch. A saved synthetic
six-scenario run under ignored `.data/phase-two-check/` preserves every worktree.
No real account-backed generation or provider request was made. Actual login,
effective sandbox/policy compatibility, and generation qualification remain Phase 5
work; the earlier account-isolation probe does not establish those results.

**Phase 3 offline evidence (2026-10-27):** 197 backend tests, Ruff and 16/16 demo
evaluations passed. One symbolic-link test was skipped because of Windows
permissions; both Windows junction regressions passed. The existing Starlette/httpx
deprecation warning remains. A separate fake app-server run exercised two
independent workers, a dependent worker starting from its prerequisite's staged
commit, an integration conflict and an out-of-scope failure. Successful phases
stopped for review; conflict/scope cases stayed blocked. Every worktree was retained
and accepted project trees remained unchanged. Reports stay ignored under
`.data/phase-three-check/`. These are offline integration checks with no provider
requests; Phase 3 user acceptance remains pending.

## Claude Code handoff

After approving and compiling the brief, set `ALLOW_CLAUDE_BUILD=true` and restart.
Click **Build with Claude Code**. The adapter:

1. Creates `.data/builds/<session-id>/r<revision>/` and writes the approved `CLAUDE.md`.
2. Initializes a repository and runs `claude -p --output-format stream-json --verbose`.
3. Uses restricted file tools, a dollar budget and a timeout; it does not bypass
   permissions, invoke shell tools, or pass the Token Factory key to the agent.
4. Saves the streamed progress log and shows the resulting `index.html` in a sandbox.

**Current build limitation:** the live adapter asks for a self-contained HTML/CSS/JS
application. It can produce browser-local apps, but does not run a generated backend
or implement cross-device synchronization. Claude is explicitly instructed to disclose
such unsupported requirements instead of simulating them. The habit-tracker fixture
also discloses that it is prebuilt and does not satisfy a user-selected sync decision.
Do not present that fixture as proof that a clarified sync requirement was built.

The embedded preview blocks network requests, navigation privileges and browser
storage. Download the HTML to run it separately and try browser-local saving.
Live CLI authentication, billing and the generated app's correctness need testing
on your machine. `--restricted` requires a recent Claude Code version; the installed
version at implementation time was 2.1.310. There are no fallback permission-bypass flags.

## How the engine works

```text
Voice or text
    |
    v
Nano extraction --> exact source-quote checks --> SQLite ledger
                                                   |
                                                   v
             Data / Access / Behaviour / Contradictions / Edges / Done-ness
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
                                cited CLAUDE.md --> coding adapter
```

The app owns ledger IDs and applies deltas atomically. Confirmation requires an exact
quote from the current user turn. A model cannot confirm an item using an assistant's
question or a quote from an unrelated turn. Inferred requirements remain unconfirmed.

The build gate requires confirmed values for goal, core flow, data, access, non-goals
and an observable success criterion; completed analysis; no conflicts; and no open
question with impact at least 12. Divergence 1 questions are dropped. Equal scores
prioritize contradictions, then question text, so critic completion order does not
change the ranking. Playback is generated after every four answered questions and
can be requested for final review. Any new utterance invalidates playback approval,
the compiled brief, and the displayed build output.

The semantic verifier rejects unsupported brief lines. Structural validation removes
invalid citations, retains all confirmed items, and renders unanswered questions and
inferences as **Undecided — choose the simplest option and report the choice**.
Citations alone are not proof of semantic fidelity: use the live evaluation and
review a sample of compiled briefs before making quality claims.

## Verification and evaluation

```powershell
uv run pytest -q
uv run ruff check backend
npm test
npm run typecheck
npm run build
npm run eval:demo
# Uses real Token Factory calls and credits:
uv run python -m backend.evals.run
```

Eight fixtures in `backend/evals/fixtures.json` contain 2–3 documented ambiguities
each. The runner compares six lenses with one general critic, keeping extraction,
ranking, required-slot fallbacks and compilation the same. The six-lens strategy
has a larger model-call and candidate budget; report spend alongside quality.

Reports are written to `.data/evals/latest.json`. They retain questions, code
differences, ledger entries, briefs, token usage, costs and planted answers. Keyword
hits are a **screening proxy**, not a measured ambiguity catch rate. Manually score
each ambiguity and semantic invented requirement from the saved report. A zero
structural citation-error count does not prove zero invented requirements.
`--demo` runs both pipelines with deterministic fixtures and measures no model quality.

## Project map

```text
frontend/app/          Conversation, ledger, playback, brief comparison, build UI
frontend/lib/          Typed API/SSE client and optional browser speech
backend/app/domain.py Ledger contracts, quote checks, ranking, gate, traceability
backend/app/engine.py  Extract -> six critics -> rank -> ask -> playback -> compile
backend/app/models.py Token Factory adapter, JSON repair and usage accounting
backend/app/demo.py   Explicit deterministic fixture provider
backend/app/store.py  SQLite persistence with short, closed transactions
backend/app/builder.py Restricted Claude Code subprocess and bounded HTML preview
backend/app/main.py   Local FastAPI routes and streamed turn events
backend/evals/        Annotated fixtures and comparison runner
backend/tests/        Evidence, gate, retry, persistence, API and evaluation tests
scripts/dev.mjs       Starts and stops the local web and API servers
```

## Scope and remaining work

Included: browser text and push-to-talk, spoken questions, live ledger updates,
one question with 2–3 options, impact inspection, playback approval, traceable brief
export, transcript comparison, persistent sessions, and the restricted coding adapter.
Browser speech depends on browser support and may use the browser vendor's recognition
service; it is not guaranteed to run locally. Text is always available.

Before submission: run the live model smoke test, tune prompts against the eight
fixtures, manually audit brief fidelity, validate microphone behaviour in the demo
browser, test the authenticated CLI path, and extend generated-app execution to a
real backend if the demo must prove cross-device sync. Speculative criticism while
the user is still speaking and instant Nano filler acknowledgments are not implemented;
the current pipeline starts after the user sends the final transcript.

Excluded: phone calls, barge-in, accounts, multi-project memory, post-build feedback,
Codex support, deployment, billing UI and pricing strategy. Post-build iteration,
multi-project memory and alternate agent adapters remain roadmap items.

This server is designed for one trusted local user and one orchestrator process.
Session locks and build jobs are process-local. The API has no account authentication;
keep it on loopback and do not publish it. Session content is stored unencrypted in
the ignored `.data/` directory. The preview is sandboxed; the Claude CLI itself is
a local process rather than a VM or operating-system sandbox.

## API references

- [Token Factory text generation](https://docs.tokenfactory.nebius.com/api-reference/examples/text-generation)
- [Token Factory structured output](https://docs.tokenfactory.nebius.com/ai-models-inference/json)
- [Token Factory model catalog](https://tokenfactory.nebius.com/model-catalog.md)
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless)
