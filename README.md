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

Graph/context verification (2026-10-28): 334 backend tests passed with one existing
Windows symlink skip and one existing deprecation warning; Ruff, 23 frontend tests,
type checking, production build and all 16 labeled demo evaluations passed. Browser
checks covered complete/blocked fixtures, identity, search, keyboard controls and
mobile/desktop layout. The browser tool blocks `file://` navigation, so opening
the exported viewer from disk with network disabled remains a manual check. No live
provider call was made for this extension; original Phase 5 qualification remains
incomplete. Checkpoints and limits are in the [current handoff](.Codex/handoffs/2026-10-28-0843.md).

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
requests. The user accepted Phase 3 on 2026-10-27.

**Phase 4 offline evidence (2026-10-27):** 217 backend tests passed, with one
Windows symbolic-link skip and the existing Starlette/httpx warning. Ruff,
15 frontend tests, TypeScript checking, the production build and all 16 scripted
demo evaluations passed. Real temporary Git repositories and fake app-server
processes cover stale review identities, rejected evidence, retained repairs,
compare-and-swap promotion, lost promotion replies, restart history inspection,
failed interruption and successor phases pinned to reviewed commits.

Production-browser simulation covered permission decline, active cancellation,
failed trusted checks, rejection/repair, acceptance, explicit next-phase blocking,
correction and reload. A labeled interrupted-dispatch fixture also showed restart
uncertainty with repair and successor dispatch disabled. Desktop and mobile layouts
were inspected. Screenshots and observations remain ignored under
`.data/phase-four-check/`. No provider requests or real account-backed qualification
were performed. Checkpoints: `c93b6cf` (backend gates) and `a87f42d` (execution UI).
The user accepted Phase 4 on 2026-10-27. Phase 5 qualification tooling is now
implemented; actual provider qualification remains incomplete.

### Phase 5 qualification commands

Run these from the repository root. They use only this server's configured key
and Codex profile. They never enable execution, change billing, sign in, approve
requirements or plans, accept phases, or create replacement sessions.

```powershell
uv run python -m backend.smoke --output .data/live-check/basic.json
uv run python -m backend.qualify_planning --output .data/live-check/planning.json
uv run python -m backend.qualify_codex --output .data/live-check/codex.json
```

The commands announce model requests before making them. Without a key, planning
writes `missing_credentials`; without the explicit execution flag, Codex writes
`execution_disabled`. Neither path makes model requests. When execution is enabled,
the Codex command first checks the existing managed ChatGPT account, profile policy,
model inventory and limits without starting a model turn. An incompatible profile
produces `profile_unavailable`; it is never replaced or silently reconfigured.

For an actual planning attempt, first create a live conversation and explicitly
approve its requirements in the app. Stop the app server before using these CLIs:
they access its SQLite store directly and must not run alongside its orchestrator.
Pass that existing session ID; its budget, reserved passes and two-attempt allowance
remain in effect. Use a separate output directory for each session so saved artifacts
from earlier probes cannot be mistaken for the current result.

An explicitly approved, one-time extension may permit a third attempt for the
same approved requirements. The normal settings maximum remains two. Both failed
attempts and all usage remain stored; the extension cannot be renewed. A correction
invalidates an unused extension. The operator command provides a read-only preflight:

```powershell
uv run python -m backend.planning_extension --session-id-file .data/live-check/SESSION_MARKER.txt --output .data/live-check/extension-preflight.json
```

Only after explicit human authorization, stop the app server and issue the grant
using the preflight's `state_hash`, the exact approval saved in an ignored UTF-8
file, the reason, and the verified implementation's full Git commit hash:

```powershell
uv run python -m backend.planning_extension --session-id-file .data/live-check/SESSION_MARKER.txt --output .data/live-check/extension-issued.json --issue --expected-state-hash 'PREFLIGHT_STATE_HASH' --approval-file .data/live-check/extension-approval.txt --reason 'Approved live requalification after a verified fix' --implementation-commit 'FULL_40_CHARACTER_COMMIT_HASH'
```

The command makes no model requests. Changed preflight state or an existing grant
blocks issuance. Generation reserves attempt 3 atomically, consumes the grant even
on interruption, and stops at the existing plan-review gate. It still has at most
nine logical passes, one JSON repair per pass, and the existing dollar budget.
The grant's private audit fields are excluded from public session/detail/events
and operator reports. See the [approved policy amendment](docs/plans/2026-10-28-planning-requalification-proposal.md).

```powershell
uv run python -m backend.qualify_planning --session-id 'YOUR_LIVE_SESSION_ID' --output .data/live-check/probe-1/planning.json
```

This writes `planning-human.md` and `planning-engineering.md` beside the report.
The plan stops at review. Restart the app, inspect both views and approve the exact
plan revision. Stop the server and rerun the same command to export
`planning-bundle.zip` without repeating model calls. Product content is confined to
these local artifacts and the session store; it is excluded from the redacted report.

For execution, use an approved live plan compatible with `git-inspection-only-v1`.
After configuring execution explicitly and stopping the server, select a phase:

```powershell
uv run python -m backend.qualify_codex --session-id 'YOUR_LIVE_SESSION_ID' --phase-id P1 --output .data/live-check/probe-1/codex.json
```

It dispatches that phase once through the existing executor, or inspects its saved
outcome if already attempted. It never automatically repairs, resumes, accepts or
redispatches an existing phase. Pending permission requests are not granted by this
CLI and can time out; use the app's normal execution flow for interactive permission
review. Restart the app to inspect evidence and accept the exact review before
explicitly starting a successor. For the live audit, use a first phase with one
package, then a successor with two independent packages. Two workers require the
existing explicit concurrency configuration and a qualified compatible profile.

Reports retain per-response planning tokens, estimated dollars and latency, including
failed planning attempts, plus observed Codex tokens separately. String fields are
allowlisted; unknown model names are redacted. Reports exclude credentials, auth
payloads, transcript bodies, account identifiers, paths and exception text. Requested
thinking controls are recorded; provider-side behavior and multiple-account inference
remain `unverified`. CLI exit 0 means its automated checks passed, not Phase 5
acceptance. The report always keeps overall `passed` false; record the manual audit
and Phase 5 acceptance separately. Missing prerequisites and failed automated checks
exit 1.

**Observed results (2026-10-27, America/New_York):** the separate basic smoke and
planning commands exited 1 with `missing_credentials`; the Codex command exited 1
with `execution_disabled`. All three made zero model requests, recorded no usage
and incurred no model spend. The managed account and effective sandbox were not
probed because execution was disabled. Reports remain ignored under
`.data/live-check/`. Offline qualifier tests cover missing prerequisites, retained
failure usage, redaction, approval gates, cleanup failures, actual Git verification
through a fake app-server, and inspection without duplicate dispatch.

Fresh verification at checkpoint `e4e5973`: 229 backend tests passed (12 qualifier
tests), one Windows symbolic-link test skipped, and the existing Starlette/httpx
warning remained. Ruff, 15 frontend tests, TypeScript checking, the production build
and 16/16 scripted demo evaluations passed. A separate loopback server started,
returned healthy demo configuration and an empty session list from a dedicated
database, and shut down cleanly. These checks made no model requests.

Live planning fidelity, exported packet audit, real Codex generation, cancellation,
reload/restart reconciliation, acceptance and correction remain pending. No live
model-quality result or Phase 5 acceptance is claimed.

**Live follow-up (2026-10-28, America/New_York):** the configured Token Factory
key authenticated and the model inventory included the configured Nano, Super and
Ultra IDs. The initial SDK connection failed certificate verification. A local PEM
bundle exported from the machine's existing OS trust roots resolved that connection
failure with TLS verification enabled. The bundle is ignored local configuration,
not a portable project dependency. Test processes used:

```powershell
$env:SSL_CERT_FILE = (Resolve-Path '.data/live-check/2026-10-28/system-trust.pem').Path
uv run python -m backend.smoke --output .data/live-check/2026-10-28/basic-after-prompt.json
```

The basic live Nano/Lightning extraction and Super contradiction smoke passed
before and after the prompt changes. Optional thinking-control probes had mixed
schema/grounding results: one failed on Lightning, a later probe failed on Nano,
and a focused Lightning recheck passed. These requests returned model responses,
but do not establish reliable control behavior. `SEND_THINKING_CONTROLS=false`
remains the application default.

A real three-turn counter clarification session exposed missing source retention,
repeated questions, inflated change-cost scores, and inaccurate playback wording.
`fc573aa` supplies the ledger and answer history to the existing ranking pass and
clarifies extraction, scoring, exclusion and playback instructions. After explicit
diagnostic re-extraction and reanalysis in the same retained session, all six slots
were filled with exact source quotes, no high-impact blockers remained, and the
corrected playback matched the access and recovery decisions. This is one observed
integration case, not a measured quality or reliability result. Grouped extraction
and semantic fidelity still need manual review. That initial clarification checkpoint
retained 54 model responses and an estimated $0.09068 in usage. The subsequent
requirements approval and planning results are recorded below.

With the user's explicit execution opt-in, the original Codex profile was rejected
for inherited tools. A separate local test profile was prepared and the user signed
in with ChatGPT through the CLI. Its browser/app/plugin features and skills were
disabled within that profile. It qualified with CLI 0.164.0, model `gpt-6.1-sol`, no
runtime MCP servers and no enabled skills. Credentials were not copied. No Codex
model turn has started; effective live sandbox behavior, generation and lifecycle
qualification remain pending. Reports stay under `.data/live-check/2026-10-28/`;
authentication state stays in the ignored test profile.

An initial regression run exposed that tests inherited the developer's live `.env`.
`eba9e0e` makes test defaults independent of that file and exported app settings,
uses an isolated test database and blocks unmocked synchronous/asynchronous HTTP
transports. The normal `uv run pytest -q` then passed **234 tests**, with one Windows
symlink skip and the existing dependency warning. Ruff, 15 frontend tests, type
checking, the production build and 16/16 demo evaluations also passed. The five new
cases cover test isolation, network blocking, mocked providers and ranking context
with failure closure. These code checkpoints are local on
`codex/phase-five-live-qualification`.

**After requirements approval (2026-10-28):** the user approved revision 3 through
chat and the approval was recorded through the production API. Ultra compiled the
brief on its first logical call and Super returned no rejected or missing brief
items. Manual review of this artifact retained the core actions, access policy,
storage behavior and exclusions; small unresolved choices stayed labeled. These
two responses cost an estimated $0.01196. The resulting local artifact is
`.data/live-check/2026-10-28/counter-brief-artifact.md`.

Live planning **did not pass**. Attempt 1 used its JSON repair, then failed confirmed
specification coverage. Application-owned confirmed/unconfirmed ID checklists and
explicit statement-status instructions were added. Attempt 2 returned schema-valid
JSON covering all seven confirmed IDs, but the application rejected its non-ASCII
architecture diagram. No outline, screen or phase was accepted. Both session
attempts were consumed at that checkpoint; no allowance was reset and no replacement
session or additional live planning request had been made.

The diagram failure exposed a schema gap: ASCII was checked only after provider
schema validation, so the existing JSON-repair path could not handle it. Checkpoint
`a0af23f` declares the ASCII pattern in the provider schema while retaining
application validation. Offline regressions verify repair of a Unicode diagram,
failure after two invalid responses, Unicode prose support, coverage checklists
and rejection of proposal-only coverage. At that checkpoint the contract fix had
not been requalified live in the exhausted session. Fresh verification passed 242 backend
tests (one Windows symbolic-link skip and the existing dependency warning) and
Ruff. No frontend files changed during this follow-up.

The compile/planning follow-up used five responses costing an estimated $0.02111;
the retained counter session totals an estimated $0.11179. Reports and redacted
field/error diagnostics are in `.data/live-check/2026-10-28/planning-attempt-1/`,
`planning-attempt-2/` and `approved-requirements-test-summary.json`. No valid plan,
plan approval, bundle audit or Codex model turn followed these failures. Phase 5
and real generated-app qualification remain incomplete.

**Approved one-attempt extension (2026-10-28):** after explicit human approval,
`ec14afd` implements one recorded, non-renewable session extension while keeping
the ordinary settings maximum at two. Prior attempts and usage remain intact;
issuance and attempt reservation use atomic snapshot checks. Correction invalidates
an unused extension, and private audit fields are excluded from public responses.
`3c86154` separates transport test startup from short fault-probe deadlines and
closes failed fixture setup; production transport deadlines are unchanged.

Final fresh checks passed: **276 backend tests**, one existing Windows symlink
skip and the existing dependency warning; Ruff, 15 frontend tests, type checking,
production build, and 16/16 labeled demo evaluations. A built-app loopback/proxy
smoke passed streamed demo planning, both views, and the approval gate. The basic
live smoke initially returned generic Nano `model_error`; an instrumented repeat
passed Nano, Lightning and Super without a runtime/prompt change. The optional
thinking-controls smoke passed too, but the default stays off and prior failures
remain evidence. The isolated Codex profile requalified without inference.

The single authorized third planning attempt **failed**. Its outline covered all
seven confirmed IDs and passed ASCII checks, and one screen was accepted. After
one JSON repair, the first phase returned `ui-setup-phase` where the accepted
outline required `ui-setup`; the application correctly rejected that identity.
The unaccepted candidate also contained shell-style checks and a placeholder
verification command incompatible with the trusted runner; none was executed.
Four Super responses cost an estimated **$0.01263540**, bringing the retained
session estimate to **$0.12442798** across 63 usage records.

The extension is consumed and all three attempts remain stored. Postflight
confirmed exhaustion blocks before provider dispatch. No complete immutable plan,
plan approval, bundle, or Codex model turn exists. The outline and screen are
partial accepted sections, not a qualified plan. Evidence is ignored under
`.data/live-check/2026-10-28/extension-attempt-3/`. At that checkpoint, no fourth
attempt, reset, or replacement session was used. Offline checks passed; live planning and
Phase 5 remain failed/incomplete.

**Offline request-contract follow-up (2026-10-28):** screen and phase requests now
require their exact accepted outline reference in the provider validation schema,
so reference drift can use the existing single JSON repair. With Codex execution
enabled, phase requests also receive the trusted runner's actual command policy;
whitespace inspection is not behavioral verification. Existing preflight and
approval gates remain in place. These changes have offline regression coverage,
not a fresh live pass. The [further qualification proposal](docs/plans/2026-10-28-fourth-attempt-requalification-proposal.md)
was subsequently approved, implemented, and consumed as recorded below.

**Fourth-attempt qualification (2026-10-28):** `af20dea` adds one separately
audited grant while preserving the consumed original extension. Atomic preflight,
issuance/reservation, historical hashes, private audit fields, correction/restart
handling, and refusal of attempt 5 have 37 new regressions. Fresh checks passed
377 backend tests, one existing skip/warning, Ruff, and all 16 labeled demo cases.

The one approved fourth attempt **failed at the outline**: its repaired response
violated the ASCII diagram schema at `architecture`. Two Super responses cost an
estimated $0.00818940, bringing retained usage to 65 responses and $0.13261738.
Both grants are consumed. Prior attempts/usage, approved requirements revision 3,
and the compiled brief are unchanged; no active plan, plan approval, or Codex turn
exists. Attempt 5 is blocked before provider dispatch. There is no automatic retry;
live planning and Phase 5 remain failed/incomplete. Evidence stays ignored under
`.data/live-check/2026-10-28/requalification-attempt-4/`.

**Offline response-boundary fixes (2026-10-28):** new provider responses now render
a finite set of common arrow/box glyphs as ASCII in diagram fields only, then apply
the original validation. Unknown characters and oversized diagrams still fail.
Source quotes, identifiers, commands and stored plans are unchanged. Repair now
addresses schema values as well as JSON structure. Planning output marked as
length-limited receives the existing single compacting repair and cannot silently
be accepted as complete. Budgets, token limits and attempt allowances are unchanged.
Integrated simulated-HTTP tests cover planning through graph/views, runner preflight,
preserved source/hash identity and gated export. These checks are not a new live pass;
the retained session remains exhausted. See the [current handoff](.Codex/handoffs/2026-10-28-0843.md).

Checkpoint `23acab5` passed 387 backend tests with one existing skip and warning,
Ruff, 23 frontend tests, type checking, production build, and all 16 labeled demo
evaluations. No new provider request was made and the retained live state is unchanged.

**Interactive graph update (2026-10-29):** the ASCII conversion described above is
superseded by bounded Unicode descriptions; the adapter preserves Unicode unchanged.
Graph sections now support cited questions, exact scoped direction, saved history,
per-section drafts and optional dictation. These changes do not authorize a fifth
planning attempt or establish live model quality. The retained live session still
has four consumed attempts and no approved plan. See the
[latest handoff](.Codex/handoffs/2026-10-29-0035.md) for final checks and publication.
Offline verification passed 415 backend tests (one existing skip and warning), Ruff,
31 frontend tests, type checking, production build and all 16 scripted demo runs.
Isolated demo browser checks covered desktop/mobile, scoped questions and direction,
draft restoration, stale gating, keyboard selection and Unicode. Speech lifecycle
was tested with simulated recognition; real microphone and live explanations remain
unverified. The retained live session's stored bytes and usage counts are unchanged.

**Fifth-attempt authorization (2026-10-29):** the human subsequently authorized one
fifth attempt to qualify the merged Unicode fixes. A separate `fifth_attempt` grant
binds the retained session, approved revision, all four prior attempt hashes and
the consumed fourth-attempt grant. Neither earlier grant is reset. The existing
local operator command accepts `--fifth-attempt` for preflight and issuance; issuance
still requires a stopped server, fresh state hash, exact approval file, reason and
verified implementation commit. The grant is consumed atomically before dispatch;
failure, interruption, restart or correction never replenishes it. The ordinary
two-attempt policy, nine-pass cap, one repair per pass and session budget remain.
No sixth attempt is provided. See the [bounded execution plan](docs/plans/2026-10-29-fifth-planning-attempt.md).

The sole fifth attempt **failed outline coverage** after one schema-valid Super
response: `common_rules` omitted L4, "No login, network, backend, or sync", although
the specification covered all seven confirmed IDs. Unicode was accepted. The call
used 2,531 input and 2,416 output tokens, costing an estimated $0.00293370; cumulative
usage is 66 responses and $0.13555108. The fifth grant is consumed. No active plan,
plan approval or coding-agent dispatch exists; attempt 6 is refused before provider
or save. Prior attempts, grants, usage, requirements revision 3, playback approval
and compiled brief were preserved. Private evidence is under
`.data/live-check/2026-10-29/attempt-5/`.

Manual inspection also found unsupported first-launch behavior: the architecture
would treat an absent saved value as a storage failure and disable both buttons.
It also promoted a non-negative-integer restriction and per-tab storage keys to
confirmed rules without explicit support. These observations are fidelity failures,
not reasons to bypass coverage validation or accept the outline.

The failure exposed a repair boundary: deterministic outline checks previously ran
after the adapter had accepted the response, so a coverage failure received no
repair. The follow-up binds the existing outline validator to the response schema
and supplies an explicit constraint-ID checklist. JSON, schema and deterministic
outline failures now share the existing single repair; two failed responses still
close the gate. This is an offline correction, not a sixth live attempt or evidence
that the model's fidelity issues are resolved. No allowance or prior failure was reset.
Checkpoint `8f51a9a` contains the audited fifth-attempt grant; `219b1eb` contains the
repair correction. Fresh verification after the correction passed 459 backend tests
(one existing Windows symlink skip and deprecation warning), Ruff and all 16 scripted
demo evaluations with zero provider calls. These checkpoints were subsequently
included in PR #4, linked below.

**Sixth-attempt qualification (2026-10-29):** the human authorized one sixth
attempt with the outline repair fix. Checkpoint `b1ab901` adds a separate audited
`sixth_attempt` grant and local `--sixth-attempt` operator mode, preserving the
ordinary two-attempt policy and every earlier grant. Its 33 new tests passed;
fresh full verification passed 492 backend tests (one existing skip and warning),
Ruff and all 16 scripted demos.

The sole sixth attempt accepted the outline and one screen, then **failed at the
first phase** with `Package misses scope exclusions`: both returned packages had
empty exclusions, missing L4 (no login, network, backend or sync). The phase had
already used its one JSON/schema repair, so no third response was permitted.
Three logical passes used four Super responses, costing an estimated $0.01181010.
Cumulative usage is 70 responses and $0.14736118. All prior evidence, approved
requirements/playback revision 3 and the compiled brief remain intact. All four
grants are consumed; attempt 7 is refused before provider/save. No complete plan,
plan approval or coding-agent dispatch exists.

The offline follow-up applies the existing deterministic checks to screen and phase
responses inside the same single repair limit, including full coverage at the last
phase. The phase prompt explicitly requires all constraint IDs in every package's
exclusions. Post-call guards and the final semantic reviewer remain; no validation
is weakened, no extra response is added, and the failed sixth attempt is preserved.
This change has no new live qualification evidence. See the
[sixth-attempt record](docs/plans/2026-10-29-sixth-planning-attempt.md); private
diagnostics remain ignored under `.data/live-check/2026-10-29/attempt-6/`.
Repair checkpoint `dfc707a` passed 512 backend tests (one existing Windows symlink
skip and deprecation warning), Ruff and all 16 scripted demos with zero provider
calls. The live sixth-attempt state is unchanged by the correction. These
checkpoints were subsequently published in
[PR #4](https://github.com/Azrkiel/Intent/pull/4), "Add audited planning retries and
bounded section repair", after the human authorized publication and merge. The PR
records the final merge state. A fresh pre-publication run passed 97 grant/repair
tests and Ruff; the fetched base matched the verified base. No seventh attempt or
coding-agent dispatch occurred.

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

Before submission: run the live model smoke test, tune prompts against the eight
fixtures, manually audit brief fidelity, validate microphone behaviour in the demo
browser, test the authenticated CLI path, and extend generated-app execution to a
real backend if the demo must prove cross-device sync. Speculative criticism while
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
