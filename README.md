# Intent

Turn a rough software idea into a brief a coding agent can build from. The application
keeps an explicit **Intent Ledger**, asks one build-changing question at a time, plays
back its understanding, and compiles a brief with a source for every requirement.
(Earlier work used the name Prompt Caller, which remains in some identifiers.)

This is a single-user MVP. The default **demo mode is scripted**: it makes no model
calls and the build preview is a clearly labeled prebuilt example. Live mode runs on
NVIDIA Nemotron through Nebius Token Factory and needs your own API key.

A hosted scripted demo runs at <https://show-intent.fly.dev>; its workspace asks you
to sign in with GitHub.

## Demo video

[Watch the 2:20 Intent demo](docs/demo/README.md). It includes the current Graph &
notes view, the saved result of a live Nebius Token Factory/NVIDIA Nemotron Nano and
Super turn with its request timing, and a labeled prebuilt preview. Silent and music
versions are available.

## What works today

| Capability | Status |
| --- | --- |
| Clarify, approve, brief, graph and notes (scripted) | Works locally and on the hosted demo; no model calls |
| Live clarification with Nano and Super | Recorded 2026-10-30: one turn, 14 HTTP 200 responses |
| Live brief compilation with Ultra, checked by Super | Ran on 2026-10-28 for a separate test session; not in the demo video |
| Live phase planning | Not passing: eight recorded attempts failed; repair fixes since are tested offline only |
| Codex worker execution | Implemented, off by default, no run from a live approved plan |
| Coding-agent build | Implemented for self-contained HTML; the demo preview is a prebuilt example |

Dated results and the full attempt history are in the
[qualification log](docs/qualification-log.md).

## How Intent uses NVIDIA and Nebius

Every live model call goes through the **Nebius Token Factory** OpenAI-compatible API to
**NVIDIA Nemotron** open models. Each model has one job:

- **Nemotron 3 Nano** extracts requirements with exact source quotes, and handles clarity checks and playback.
- **Nemotron 3 Super** runs six concurrent critics, then ranks the single next question and verifies the brief.
- **Nemotron 3 Ultra** compiles the approved brief, once per session.

Where Token Factory helped:

- One endpoint and one key reach all three model sizes, so Intent needed no inference
  infrastructure of its own.
- Routing is configuration: model IDs and the base URL live in `.env`, which also let
  the smoke test compare Nano against `nvidia/Nemotron-3_5-Lightning` as an extractor.
- Concurrent requests keep six critic perspectives practical. In the recorded turn they
  started together and took 6 to 18 seconds. The whole turn took about two minutes and
  an estimated $0.016.

Intent uses no other Nebius service. The orchestrator owns ledger IDs, source checks and
readiness; models return validated changes and never replace the ledger. See
[How the engine works](#how-the-engine-works) and the [model routing table](#connect-nemotron).

## Run locally

Prerequisites: Node.js 22+, Python 3.11+, [uv](https://docs.astral.sh/uv/), and Git.
For live builds, install and authenticate the [Claude Code CLI](https://code.claude.com/docs/en/overview).

```powershell
uv sync --group dev
npm ci
npm run dev
```

Open **http://127.0.0.1:3000** for the Intent homepage, then choose **Workspace**
(or open **http://127.0.0.1:3000/workspace** directly). The workspace sidebar connects
the conversation, build brief, project graph, Codex execution, and build output.
The orchestrator runs on port 8000; interactive API
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
unverified. Calls with an 8192-token output limit (clarity, framework map, compiler)
wait 120s instead of 45s: with provider-default thinking, live Nano clarity passes ran
up to 43s. `NANO_THINKING_OFF=true` sends the thinking-off control for Nano `clarity:*`
passes only. It cut the rubric pass from about 23s to 7s in a live A/B (2026-10-30), but
the judge then failed W1 on "I" in 3/3 runs and misjudged a clear ambition, so it stays
off by default. Thinking off also made the extractor return slot names as ledger types. All model IDs and the API base URL can be changed in `.env`.

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

### Framework-backed clarity

Live readiness also requires a current product framework and an independent review.
After extracting intent and running the six critics, Super drafts eight connected
areas: purpose/users, end-to-end journeys, component structure, data lifecycle,
access, failure/recovery, acceptance checks, and scope. Each area has named aspects
and cited statements. Concrete implementation defaults are labeled **proposals**;
they do not become confirmed user requirements. A separate Super pass checks the
entire map for specificity, consistency, missing behavior and unsupported commitments.

The server requires every area/aspect, coverage of every confirmed requirement,
valid citations and a review of every map entry. Critical framework questions remain
blocking independently of the question ranker. Vague six-slot coverage alone cannot
reach 100% in live mode. Failed/partial reviews, missing details, conflicts and stale
source revisions keep readiness blocked. New utterances and analysis retries clear
the old review. Older live sessions need reanalysis before new approval or building.

The workspace's **Product framework** panel exposes the map, proposed choices and
remaining blockers. **Review framework again** reruns analysis after a failed or
inadequate map. A successful reviewed map accompanies the brief and is supplied as
proposal context to the later phase planner. User playback approval still precedes
compilation and phase planning; framework review does not approve execution.

These two extra model passes share the existing session budget and request limits.
When the reviewer finds a map defect that needs no user decision, Intent makes one
bounded map/review repair attempt. Remaining defects still block readiness.
They use the existing Super route; mapper output is bounded at 8192 tokens. Reasoning
controls retain their configured provider-compatibility behavior. No artificial delay
or reasoning-mode switch substitutes for coverage and review checks.

Demo mode shows a **scripted example**, including canned implementation proposals.
It makes no reasoning calls and is not evidence of product-specific understanding.
Historical demo fixtures retain their scripted checklist behavior. Offline regression
tests verify the gate and lifecycle, not actual provider judgment or product quality.

The semantic verifier rejects unsupported brief lines. Structural validation removes
invalid citations, retains all confirmed items, and renders unanswered questions and
inferences as **Undecided — choose the simplest option and report the choice**.
Citations alone are not proof of semantic fidelity: use the live evaluation and
review a sample of compiled briefs before making quality claims.

### Clarity v2

Clarity v2 is a per-session version, fixed when the session is created like `mode`. Live sessions
default to v2 and demo sessions to v1 (the scripted demo and the 16 scripted evals stay on v1).
`CLARITY_VERSION=1|2` overrides the default, and `POST /api/sessions` accepts an optional body
`{"clarity_version": 1|2}`. Historical sessions stay on v1.

**North Star.** Six fields must each pass: who and when, the job, ambition, today, what good looks
like, and what fails it. A field passes only when all its checks pass: G1 (deterministic lexicon
prompts for vague, escape, open-ended, absolute and subjective wording; non-blocking, prompted once),
a rubric judge, G3 (the user confirms a read-back of the field) and G4 (two independent readers
agree, Krippendorff alpha at or above `CLARITY_ALPHA_PASS`, default 0.80; the floor is
`CLARITY_ALPHA_FLOOR`, default 0.667). There is no question cap. Every follow-up for a
failing field carries Intent's extrapolated drafts and the assumptions behind them; the user picks
one, edits it or writes their own. A field built only from picked drafts skips G3, but the rubric and G4
still run. Claims carry computed provenance (quote tiling and a novelty tripwire).

**Decisions.** Build-changing choices are discovered by divergence between candidate builds, scored,
and then asked, delegated, deferred (with a `due_phase`) or excluded. Choices Intent makes for the
user are listed and can be vetoed. Planner-side enforcement of `due_phase` is not implemented.
Settings: `DECISION_STOP_THRESHOLD` (default 1.5) and `DECISION_REPEAT_PENALTY` (default 0.5).

**Scenarios and review.** The user approves concrete scenarios, plus what Intent filled in, instead
of a prose playback. In v2, `POST /api/sessions/{id}/approve` requires a ready gate and current
clarity with at least one scenario. A canary review plants known defects and measures recall;
`CANARY_CRITICAL_RECALL` (default 1.0) and `CANARY_OVERALL_RECALL` (default 0.80) set the thresholds.

**Routes.** `POST /api/sessions/{id}/clarity/readback` (`field`, `text_hash`, `revision`) confirms a
read-back. `POST /api/sessions/{id}/clarity/veto` (`decision_id`, `revision`) vetoes a choice Intent
made. The public session adds `clarity_version`, `clarity`, `readbacks`, `vetoes` and
`clarity_readout` (`statements`, `unmapped_words`, `choices_made`, `decisions_open`, `scenarios`).
The workspace Clarity panel (frontend phase P6) shows these fields, read-backs, choices with veto,
scenarios and review status; it is not described here as browser-verified.

**Evidence limits.** Offline tests, demo mode and scripted evals do not establish live model
quality. `python -m backend.evals.run --demo --clarity-version 2` reports clarity metrics (fields
passed, alpha, claims, decisions, canary recall, wasted questions) with a simulated user confirming
read-backs; it checks plumbing only. The offline HTTP-contract test runs on v1; there is no offline
v2 HTTP-contract test yet. No live qualification has been run for v2.

## Visual phase plans and instruction bundles

Open **Project graph** (or **Explore project graph** from the compiled brief).
A draft-vision root is available before a plan exists. After approving the current
requirements playback, choose **Generate phase plan**.
Validated outline, wireframe, and phase sections appear progressively. Switch
between **Project graph**, **Vision & wireframes**, and **Engineering & work
packages** to inspect the same revision. The graph starts at the project root;
use search, filters, the keyboard outline, and the node inspector to reach every
scope, source quote, acceptance condition, proposed check, and planned handoff.
Use **Fit** for the whole overview or **Center root** to return to the project
intent and orchestration. Proposed choices and unresolved questions remain explicit.

Select a node and use **Discuss this section** to ask about that part or add your
direction. Questions use the section, its ancestors and cited requirements without
changing intent or approvals. Live explanations use Super and the existing session
budget; demo explanations are labeled and scripted. **Add direction** previews your
exact words before saving them as a scoped user turn through normal intent analysis.
It clears approvals, stops affected execution and makes the old plan read-only.
Use **Shape your current draft vision** to continue while reviewing a stale plan.
Generating and approving a replacement plan remain explicit actions.

Each section keeps its own saved conversation and browser draft. Reloading a saved
request reuses its ID; interrupted requests are never automatically replayed. For a
server-confirmed uncertain result, **Start a different message** leaves the original
in history. Dictation is optional, uses the browser speech service and leaves an
editable transcript; sending still requires a click. Plain text descriptions,
Unicode arrows and multilingual labels are supported. Diagrams are optional;
control characters and oversized descriptions remain invalid.

The source-bound API is `GET /api/sessions/{id}/discussion?node_id=root` (or
`node_id=intent` for the current vision), followed by `POST` to the same path with
`{request_id,target,mode,text}`. Echo the exact GET target; mode is `question` or
`direction`. Stale sources, mismatched reused IDs and cross-mode writes are rejected.

Choose **Approve this revision**, then **Export instruction bundle**. The ZIP
contains the canonical `plan.json`, a hashed manifest, cited specification, vision,
wireframes, architecture, shared `AGENTS.md`/compatible `CLAUDE.md`, and detailed
phase and work-package packets. Approval binds the plan ID, revision, content hash,
and requirements revision. A new utterance clears approval and preserves the old
plan for inspection. Draft, failed, or stale plans cannot export.

The human ZIP also contains `graph/graph.json`, per-node JSON, and a self-contained
`graph/index.html` viewer with no remote assets. Every member is manifest-hashed.
This complete human archive is distinct from the scoped worker bundle. Partial
attempts show accepted sections and pending nodes; rejected phase bodies never
appear as validated graph content. Drawing or filtering the graph makes no model
requests and does not change the plan hash or grant execution approval.

Planning uses Super through the existing model adapter and session budget. It does
not consume another Ultra compiler pass. An attempt has an outline pass, up to
three screen passes, up to four phase passes, and one semantic verification pass;
each allows the existing single JSON repair. Defaults allow two attempts per
session, with all reservations and response usage preserved across failure,
correction, interruption, and restart. `PLANNING_MAX_ATTEMPTS` (1–2) and
`PLANNING_MAX_PASSES` (1–9) can lower these limits. Each phase holds at most two
packages and each package at most three ordered leaf tasks. Exceeding a bound
blocks the plan rather than silently dropping work.

## Editable Markdown vault and graph

Open **Workspace → Project graph → Graph & notes**. The vault works
before a phase plan exists: edit the main `Plan.md` note and create your own notes.
After generating a phase plan, choose **Add phase plan** to add linked vision,
specification, architecture, screen, phase, work-package and task notes. This is a
snapshot; later plan revisions do not overwrite your Markdown edits.

- Drag a node to arrange it, drag the background to pan, and scroll to zoom. The
  larger green node is the main plan. Click a node to read or edit its Markdown.
  Use the expand button for the full workspace, and Fit to bring notes into view.
- Connect notes with `[[Note name]]`, `[[folder/Note#Heading|Label]]`, or
  `[Label](relative/Note.md)`. Hover highlights connections; the inspector lists
  backlinks. A dashed node represents a missing note; select it to create the note.
- Create, rename or delete notes through the explorer and inspector. Renaming
  updates resolved internal links, including relative links when moving a note to
  another folder. Deleting a note keeps incoming links as missing-note placeholders.
  The main plan note can be edited and renamed, but cannot be deleted.
- Changes autosave locally. **Saved locally** confirms the saved copy; an unsaved
  draft can be exported separately. Concurrent saves show a conflict and preserve
  the draft, with backup, retry and explicit reload options. A temporary browser
  recovery copy also protects pending edits when switching views.
- **Export vault** downloads Markdown files and `intent-vault.json` in a ZIP.
  Unzip it into a folder to open in Obsidian. **Import Markdown / ZIP** replaces
  the current vault after confirmation; imported notes never count as an approved
  execution plan. Import/export supports Markdown text, not attachment files or
  Obsidian settings. The live workspace is stored in the local SQLite database;
  it does not watch or synchronize an existing filesystem vault.

Search filters both the file list and graph. Graph settings include node types,
labels, arrows, node size, link distance and repulsion. Pause/resume controls layout
motion, and reduced-motion preferences disable animated settling. Focus the graph
and use arrow keys to pan, `+`/`-` to zoom, and Home to fit. The explorer provides a
keyboard-accessible alternative to selecting graph nodes.

Vaults support up to 500 notes, 100 KB UTF-8 per note and 2 MB total Markdown.
The graph displays at most 750 nodes (including missing notes) and 5,000 connections;
an explicit notice appears at that limit, and exports retain all note content.
Raw HTML is disabled in preview. ZIP imports are bounded and validated without
extracting files onto the host filesystem.

Vault edits are independent of the canonical plan, its hash, ledger citations,
requirements approval and execution gates. Demo, draft and stale source snapshots
remain labeled. Markdown links express note relationships, not execution permission
or verified work-package dependencies.

For a second local instance, run the backend with `FRONTEND_PORT` set to the chosen
web port, and start Next.js with `INTENT_API_PORT` set to the chosen API port. For
example, use separate terminals from the repository root:

```powershell
# API terminal
$env:FRONTEND_PORT = '3001'
$env:DATABASE_PATH = '.data/second-instance.sqlite3'
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8001

# Web terminal
$env:INTENT_API_PORT = '8001'
npm exec --workspace frontend -- next dev --hostname 127.0.0.1 --port 3001
```

Defaults remain loopback ports 3000/8000. The alternate origin is restricted to
`127.0.0.1` or `localhost` at the configured web port.

## Codex execution and phase staging API

Phase 2 is implemented and verified offline against synthetic app-server processes
using the CLI schema (now pinned to 0.165.0; see `QUALIFIED_VERSION`). It adds initialization, account/model/policy
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
| `GET` | Durable runs, phases and context reviews, staged evidence, usage, permissions, changed paths, and labeled worker claims |
| `POST /contexts/prepare` | Exact approved plan identity, `package_id`, and explicit `publications` selections; save a packet without dispatching |
| `POST /contexts/{context_hash}/approve` | Exact plan identity and `packet_hash`; approve the displayed immutable input |
| `GET /contexts/{context_hash}/bundle` | Export the current approved scoped worker ZIP |
| `POST /phases/{phase_id}/start` | Exact approved plan identity and optional `model`; explicitly start the current phase scheduler |
| `POST /phases/{phase_id}/resume` | Exact plan identity and optional `model`; explicitly resume an `awaiting_context_review` phase after reviewing its eligible packets |
| `POST /phases/{phase_id}/review` | Exact plan identity, `evidence_hash`, `decision: accept\|reject`, optional `notes`; accept only the reviewed staging commit |
| `POST /phases/{phase_id}/repair` | Exact plan identity, current `attempt`, `evidence_hash` (nullable before review), optional `model`; preserve old work and start fresh package attempts |
| `POST /phases/{phase_id}/cancel` | Exact plan identity; stop phase dispatch and preserve work |
| `POST /phases/{phase_id}/reconcile` | Exact plan identity and nullable `evidence_hash`; inspect an uncertain promotion or resume known completed work; never reopen rejected evidence |
| `GET /phases/{phase_id}/artifacts/{path}?evidence_hash=...` | Download bytes from the immutable reviewed Git commit after checking their SHA-256 hash |
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

Before dispatch, prepare and review each eligible package's context in the
**Codex execution** panel. `ancestor-context-v1` supplies controlled instructions,
flat project-root and assigned-phase bodies, the complete assigned package and
its ordered tasks, applicable exact source quotes, and a handoff template. Sibling
and cousin task bodies are excluded. This restricts supplied documents; it does
not isolate filesystem reads from other source files in the checkout.

For each dependency, explicitly select the producer artifacts to publish. A shared
snapshot binds the declared interface/version, selected UTF-8 artifact bytes and
hashes, producing run, integrated commit, and trusted evidence. Missing or changed
inputs block preparation. Cross-phase inputs also require prior phase acceptance.
The input packet is limited to 262144 UTF-8 bytes; oversized packets fail without
truncation. Unsupported or placeholder checks fail preflight before Codex starts.

Context approval binds the plan, phase attempt, input base, instruction policy,
configured worker limits, snapshot hashes, manifest, and exact dispatch text.
Approval does not start a worker. Changed inputs require a fresh review. A started
phase pauses at `awaiting_context_review` when its next eligible package lacks an
approved packet; approve that packet and explicitly resume the same phase attempt.
The executor persists and dispatches those exact bytes and checks their identity
again on recovery and phase review. Historical packets remain readable after an
instruction update, while incompatible or legacy contexts cannot resume execution.

The scheduler runs only the current phase and stops at `awaiting_phase_review`.
The **Codex execution** panel restores progress, permissions, logs, diffs, trusted
checks and artifact downloads. Acceptance and rejection name an immutable review
hash covering the exact plan, phase attempt, staging commit, package attempt IDs,
check results, artifact hashes and unresolved decisions. Acceptance advances
`refs/heads/accepted` with a compare-and-swap operation; the management checkout
stays at its existing tree. Generated source remains in retained worktrees.
Acceptance enables an explicit next-phase start and never launches it automatically.
Rejection requires new repair attempts; prior reviews and changes remain retained.

Startup inspects saved Codex thread/turn history before enabling dispatch. A known
completed turn can return to verification; a running, missing or unknown turn stays
blocked for explicit reconciliation. An uncertain promotion is never replayed;
explicit reconciliation checks the saved review and actual accepted ref. Uncertain
integration still blocks repair and requires inspection of retained work. Cancelled
turns can be inspected without resuming them. A failure or cancellation stops affected
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

**Windows worker sandbox:** workers run under MXC with an allowlist from
`backend/app/codex/sandbox.py`: no network including loopback, writes only to the
worktree, reads only from the worktree, its project, Program Files and the tools on
PATH. The profile check rejects `unelevated`, `elevated` and `sandbox_mode`, and no
legacy `sandbox` or `sandboxPolicy` is sent, because each would replace the allowlist.
Inside workers `fs.realpathSync` still fails on the drive root, so Node tools that
call it (some bundlers) need checking on a real project.

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

## Verification and evaluation

Full live and offline results are in the [qualification log](docs/qualification-log.md),
along with the Phase 5 qualification commands.

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

For browser regression checks, install Chromium once with
`npx playwright install chromium`, then run `npm run test:e2e`. Stop the frontend
dev server first: browser tests and production builds use `frontend/.next`.
The browser suite starts isolated demo servers on loopback ports 3817 and 8817,
stores its temporary databases and screenshots under `.data/`, and makes no
provider calls. It checks homepage navigation, both graph views, plan approval,
section questions, linked Markdown creation, autosave, reload, execution-panel
navigation, and mobile canvas width.

**Graph integration verification (2026-10-29):** 539 backend tests passed with one
skip; 44 frontend tests and all three browser checks passed, along with Ruff,
TypeScript, the production build for `/` and `/workspace`, and 16/16 scripted demo
evaluations. Editable notes preserve the canonical plan hash and approval. These
are offline and scripted-demo checks; live provider quality and paid worker
execution remain separately qualified.

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

Remaining work: tune prompts against the eight fixtures, manually audit brief fidelity,
validate microphone behaviour, test the authenticated CLI path, and extend
generated-app execution to a real backend for cross-device sync. Speculative criticism while
the user is still speaking and instant Nano filler acknowledgments are not implemented;
the current pipeline starts after the user sends the final transcript.

Excluded: phone calls, barge-in, accounts, multi-project memory, post-build feedback,
deployment, billing UI and pricing strategy. Post-build iteration,
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
