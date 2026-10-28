# Implementation plan: visual phase plans and local Codex orchestration

Date: 2026-10-26 (America/New_York).
Status: Phases 1 and 2 accepted by the user on 2026-10-27 (America/New_York).
Phases 3 and 4 were accepted by the user on 2026-10-27. Phase 4 is implemented
and verified offline. Phase 5 qualification tooling is implemented and tested
offline. The 2026-10-28 live follow-up passed the basic Nebius smoke and qualified
an isolated signed-in Codex profile; planning and generation remain pending approvals.
Source: [design](../specs/2026-10-26-phase-plans-codex-orchestration.md).

**Goal:** Turn approved, cited requirements into synchronized design and engineering
views, export complete worker instructions, and execute dependency-safe phases
through local Codex with explicit user acceptance between phases.

**Architecture:** Keep the ledger and its approval gate authoritative. Add a planning
package for validated proposals, immutable plan revisions, deterministic rendering,
and exports. Add a separate Codex transport and execution package after export works;
the scheduler owns dispatch, evidence, recovery, and phase gates.

**Tech stack:** Existing Python 3.11+/FastAPI/Pydantic/SQLite backend, Next.js
16/React 19/TypeScript frontend, pytest/Ruff/Vitest, Git worktrees, and Codex
app-server over stdio. The installed Codex CLI inspected for this plan is 0.164.0.

## Starting point and execution boundary

- Repository: `C:/Users/jiang/Intent`; clean branch `design/phase-plans-codex`
  at `b004354` when this plan was prepared.
- Existing code compiles an approved ledger into a cited brief, then optionally
  invokes the restricted Claude HTML builder. Neither planning nor Codex execution
  is implemented. Keep the existing path available while adding the new path.
- Requirements approval, plan approval, permission approvals, and phase acceptance
  are separate decisions. Never copy one approval into another field.
- Deliver and review the five phases below in order. Each checkpoint is a small,
  separately verified commit; a checkpoint is not a user phase-acceptance gate.
- Before runtime edits, use a `codex/` feature branch and the worktree workflow.
  Read repository `AGENTS.md`, and `frontend/AGENTS.md` plus installed Next.js guides
  before frontend edits. This document does not authorize a push, merge, or release.
- Actual Nebius qualification remains pending. The missing key does not block
  fixtures, export, fake app-server tests, or deterministic scheduler tests.

```text
[Approved ledger + current requirements revision]
                       |
                       v
[Start bounded planning attempt; persist pass reservations]
                       |
       failure/limit --+--> [Blocked; save usage and accepted sections]
                       |
                       v
[Validate outline -> screens -> phases -> semantic verification]
                       |
        invalid -------+--> [Draft/blocked; approval and dispatch disabled]
                       |
                       v
[Immutable plan revision + content hash]
              /                       \
             v                         v
[Human prose + wireframes]    [Engineering graph + work packets]
              \                       /
               v                     v
                [User approves this hash]
                    /             \
                   v               v
             [Export ZIP]   [Select eligible phase]
                                   |
                    missing dependency/limit --> [Blocked]
                                   |
                                   v
                     [Separate worker worktrees/threads]
                                   |
                    timeout/cancel/error --> [Preserve work; stop dispatch]
                                   |
                                   v
                      [Inspect patch + trusted checks]
                                   |
                         failed ---+--> [Blocked; repair current phase]
                                   |
                                   v
                      [Diff + evidence + open decisions]
                                   |
                        rejected --+--> [Revise current phase]
                                   |
                                   v
                         [User accepts current hash]
                                   |
                                   v
                       [Next phase becomes eligible]

[Any new utterance] --> [Invalidate dependent approval; mark stale]
                                 |
                                 v
                   [Stop dispatch; interrupt affected turns]
                                 |
                                 v
                   [Preserve all changes for inspection]

[Restart/reconnect] --> [Read durable run + Codex history]
                                  |
                       uncertain -+--> [Blocked; never duplicate dispatch]
                                  |
                                  v
                         [Resume known lifecycle]
```

## Proposed implementation defaults

These are bounded initial policies for review, not user-confirmed product
requirements. Surface them as proposals in generated plans when relevant.

| Concern | Initial policy |
| --- | --- |
| Plan size | At most 4 phases, 2 work packages per phase, 3 leaf tasks per package, and 3 screens; reject excess instead of truncating |
| Nesting | Phase -> package -> leaf; a package is the dispatch unit and its leaves run in order |
| Planning passes | `planner:outline`, up to 3 `planner:screen:<ref>` passes, up to 4 `planner:phase:<ref>` passes, then `planner:verify` |
| Planning allowance | At most 9 logical passes per attempt, 2 attempts per session; each pass permits only the existing single JSON repair |
| Model routing | All planning passes use Super through `LiveModels.call`; no new Ultra/compiler pass |
| Spend | Existing `SESSION_BUDGET_USD` and reservations include every planning response, including invalid JSON and repair |
| Concurrency | 1 worker first; configurable 1 or 2 only after isolation checks pass |
| Codex access | Explicit `ALLOW_CODEX_EXECUTION=false` default; existing Codex-managed ChatGPT sign-in; no automatic billing-provider change |
| Execution roots | App-owned Git repositories under ignored `.data/projects/`; workers under `.data/worktrees/`; no arbitrary browser-supplied target path |
| Approval identity | Plan ID + plan revision + content hash + requirements revision |
| Preview | Preserve HTML-only preview; other generated projects expose source and evidence without claiming a running backend |

Failed attempts consume their reservations. Restoring a session preserves allowance
and usage. Reposting a successful attempt returns its stored result. A failed
attempt can only be retried explicitly within the remaining allowance. A correction
does not replenish allowance. UI errors must explain exhaustion without offering
automatic new sessions or hidden retries.

## File ownership and dependencies

New directories are packages with `__init__.py`. Keep pure contracts free of
`Session` imports: `domain.py` will import planning envelopes, so importing
`domain.py` back from those contracts would create a cycle.

| Files | Responsibility | First checkpoint |
| --- | --- | --- |
| `backend/app/planning/contracts.py` | Bounded proposal, canonical plan, attempt, approval, and section contracts | 1.1 |
| `backend/app/planning/validation.py` | ID assignment, reference resolution, coverage, DAG, path/interface ownership | 1.2 |
| `backend/app/planning/render.py` | Pure human/engineering text and package rendering | 1.3 |
| `backend/app/planning/export.py` | Deterministic ZIP, safe artifact names, manifest/hashes, controlled instruction templates | 1.3 |
| `backend/app/planning/service.py` | Bounded passes, section acceptance, semantic gate, persistence | 1.4 |
| `backend/app/planning/prompts.py` | Named planning prompts and data/instruction separation | 1.4 |
| `backend/app/planning/routes.py` | Planning SSE, detail, approval, and bundle endpoints | 1.5 |
| `backend/app/domain.py`, `engine.py`, `store.py` | Session defaults, correction invalidation, immutable plan snapshots | 1.1 / 1.4 |
| `backend/app/main.py`, `settings.py`, `models.py`, `demo.py` | App lifecycle, bounded policy, model routing, labeled fixtures | 1.4 / 1.5 |
| `frontend/lib/planning.ts`, `planning.test.ts` | Typed plan API/events and UI eligibility selectors | 1.6 |
| `frontend/components/plan-panel.tsx`, `frontend/app/page.tsx`, `globals.css`, `frontend/lib/types.ts` | Progressive synchronized views, plan approval, export | 1.6 |
| `backend/app/codex/protocol.py`, `transport.py` | Version-qualified envelopes, process/JSONL lifecycle | 2.1 |
| `backend/app/codex/client.py` | Account, threads, turns, permissions, event routing, reconciliation | 2.2 |
| `backend/app/execution/contracts.py`, `store.py`, `worker.py`, `routes.py` | Durable run attempts and one-package execution | 2.3 |
| `backend/app/execution/worktrees.py`, `scheduler.py` | Single-worker worktree creation, isolation hardening, dependency claims, two-worker scheduling | 2.3 / 3.1 / 3.2 |
| `backend/app/execution/verification.py`, `review.py` | Trusted evidence, integration, phase acceptance, invalidation | 3.3 / 4.1 |
| `frontend/lib/execution.ts`, `execution.test.ts`, `frontend/components/execution-panel.tsx` | Progress, approvals, cancellation, evidence, phase acceptance | 4.2 |
| `backend/tests/planning_fixtures.py`, `backend/tests/fixtures/codex/` | Synthetic, redacted contracts; no account or session data | 1.1 / 2.1 |
| `backend/qualify_planning.py`, `backend/qualify_codex.py`, `README.md` | Explicit live qualification and honest status | 5.1 |

No workers edit shared files concurrently. Contracts are integrated before dependent
packages are assigned. For this repository's implementation, `main.py`, `domain.py`,
`store.py`, and `page.tsx` changes are sequential integration work.

## Phase 1: structured planning, synchronized views, and export

### 1.1 Bounded contracts and backward-compatible persistence

- [x] Add `backend/tests/test_plan_contracts.py` and
  `backend/tests/test_plan_store.py`. First failing cases: old session JSON loads
  with no plan; provider-supplied canonical IDs/status/approvals are forbidden;
  empty steps/checks, excessive nesting, and size limits fail validation; immutable
  snapshots survive SQLite reopen without computed output fields being persisted.
- [x] Add proposal contracts in `planning/contracts.py` using Pydantic
  `ConfigDict(extra="forbid")`. Use proposal references separately from application
  IDs. Every cited statement carries `ledger_ids`; every decision declares
  `confirmed`, `proposal`, or `unresolved`. Confirmed statements may reference only
  confirmed source items. Open/inferred items remain visible separately.
- [x] Define `OutlineProposal`, `ScreenProposal`, `PhaseProposal`,
  `PackageProposal`, `LeafTaskProposal`, `PlanVerification`, `PlanDocument`,
  `PlanAttempt`, and `PlanApproval`. Bound strings, arrays, ASCII diagrams, inputs,
  outputs, interface references, required artifacts, and expected check results.
  Each package includes the full contract from the design: goal, citations,
  preconditions, dependencies, owned paths, consumed/produced interfaces, ordered
  leaves, happy/failure flow, acceptance, exclusions, proposals, and open questions.
- [x] Add `PlanningState` to `Session` with an optional active plan reference,
  durable attempts, and no approval by default. Add an immutable `plans` table in
  `Store` keyed by `(session_id, plan_id, plan_revision)`. Store content hash and
  requirements revision. Updating an existing revision's content is an error;
  mutable attempt/approval state lives outside the immutable plan body.
- [x] Establish canonical hashing with this exact encoding; never hash mutable
  run state, UI text caches, approval metadata, or the hash field itself:

```python
import hashlib
import json


def content_hash(content: dict) -> str:
    encoded = json.dumps(
        content, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

- [x] Run `uv run pytest backend/tests/test_plan_contracts.py backend/tests/test_plan_store.py -q`.
  Expect initial import failures, then all new tests passing. Run
  `uv run pytest -q` and `uv run ruff check backend`; all existing tests must pass.
  Commit: `feat: add versioned planning contracts and persistence`.

### 1.2 Application-owned IDs and deterministic validation

- [x] Add `backend/tests/test_plan_validation.py` with valid and adversarial
  fixtures. Cover unknown/duplicate references, references changing between
  sections, unknown ledger citations, missing confirmed requirements, self/cyclic
  dependencies, backward phase dependencies, conflicting interfaces, and path
  collisions on both Windows and POSIX.
- [x] Implement `accept_outline`, `accept_screen`, `accept_phase`, and
  `validate_plan` in `planning/validation.py`. Intent allocates plan IDs and stable
  `P1`, `P1-W1`, `P1-W1-T1` identities from an accepted outline. Models cannot add
  undeclared phase references in later passes. Persist the reference mapping.
- [x] Require every confirmed ledger ID to appear in the cited specification;
  every actionable confirmed requirement must map to a package's acceptance
  criteria. Constraints/non-goals must also appear in common rules and applicable
  scope exclusions. A source link alone is not semantic validation.
- [x] Normalize owned paths as relative POSIX paths for generated projects; reject
  absolute/drive/UNC paths, traversal, NUL, backslashes, reserved Windows names,
  trailing spaces/dots, ADS colons, wildcard ownership, and case-insensitive
  collisions. Directory ownership conflicts with all descendants. Shared
  interfaces have one producer and explicit consumers depending on that producer.
- [x] Test package DAGs and phase DAGs independently. Same-path work may run
  sequentially through an explicit dependency; unordered overlaps block approval.
  Reject unknown or incompatible interface versions. Empty ownership is invalid.
- [x] Run `uv run pytest backend/tests/test_plan_validation.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`. Expect deterministic results
  regardless of proposal ordering. Commit: `feat: validate plan provenance and dependency ownership`.

### 1.3 Deterministic renderers and portable instruction bundle

- [x] Add `backend/tests/test_plan_render.py` and `test_plan_export.py` using a
  two-phase synthetic plan with shared contracts before independent UI/API work.
  Assert both views, each phase, and every packet identify the same plan revision,
  hash, IDs, and source requirements. Assert proposals/open questions remain visible.
- [x] Implement pure `render_human`, `render_engineering`, `render_phase`, and
  `render_package` functions. Include empty/loading/error/success screen states
  when applicable; a screen-free project explicitly declares no screens. Preserve
  plain-text wireframes and happy/failure diagrams; escape when shown in HTML.
- [x] Implement `export_bundle` entirely from a validated, approved immutable
  document. Produce the exact design inventory: `plan.json`, `manifest.json`,
  `VISION.md`, `SPEC.md`, `WIREFRAMES.txt`, `ARCHITECTURE.txt`, `AGENTS.md`,
  `CLAUDE.md`, and each phase/package's `PLAN.md`, `DIAGRAM.txt`, `TASK.md`, and
  `CONTEXT.md`. The compatibility `CLAUDE.md` points to shared `AGENTS.md` rules.
- [x] Build instruction policy from application-controlled templates. Quote user
  data in explicitly delimited sections; it cannot select permissions, models,
  sandbox flags, destination roots, or automatic delegation. Tell workers they
  share a project, must preserve other workers' changes, and must report scope
  deviations. Pass common rules and assigned packets explicitly at dispatch.
- [x] Use fixed ZIP metadata and sorted member names. Compute SHA-256 over exact
  UTF-8 bytes. The manifest inventories and hashes all other members, and names
  itself without a self-referential digest. Do not serialize a `Session`, its
  usage, environment, local paths, auth state, or Codex transcripts into exports.
- [x] Reject traversal/case collisions and instruction filename injection before
  archive creation. Test tampering, malicious titles, unsafe names, deterministic
  bytes, missing approval, mismatched hash, and stale requirements revision.
- [x] Run `uv run pytest backend/tests/test_plan_render.py backend/tests/test_plan_export.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: render synchronized plans and export worker instruction bundles`.

### 1.4 Bounded planning passes, usage, and correction invalidation

- [x] Add `backend/tests/test_planning_service.py` and extend
  `test_models.py`/`test_offline_pipeline.py`. Failing cases cover failure in each
  named pass, invalid JSON plus repair, budget exhaustion, persistence between
  sections, repeated generation, concurrent duplicate requests, attempt limits,
  correction after approval, and semantic rejection despite complete citations.
- [x] Add bounded settings for the proposed limits above. Keep `LiveModels.call`
  as the only provider-call path. Assert planning roles route to Super with its
  existing token/thinking settings and share `session.usage` and reservations.
  Do not modify the one-logical-Ultra-compiler-pass policy or reset `compiler_calls`.
- [x] In `PlanningService`, require `gate_for(session).ready` and current
  requirements approval before starting. Reserve and persist each named logical
  pass before calling it. Save usage in `finally`, as `Engine.call` already does.
  Same-session mutations use the same lock as utterances and compilation.
- [x] Generate outline, then each screen, then each phase. Each complete response
  is structurally validated, atomically persisted, and emitted as an accepted
  section. Show a pending outline skeleton but never treat missing phase tasks
  or raw provider JSON as executable. A disconnected streaming request must leave
  durable state recoverable, release locks, and record interruption.
- [x] Run the final `planner:verify` over all cited statements and acceptance
  mappings, including proposals versus confirmed decisions. Use stable statement
  IDs in its result. Any unsupported statement, missing requirement, invalid
  verifier reference, verifier failure, or deterministic validation error prevents
  `review_ready`. Do not silently delete rejected material and approve the rest.
- [x] On a new utterance, mark the plan stale, clear plan approval, and preserve
  snapshots and usage. Once execution exists, also stop new dispatch and request
  interruption of affected workers. Do not erase completed work or evidence.
- [x] Add synthetic planning responses to `DemoModels` keyed by the same roles.
  Demo responses and exported plans carry a visible demo designation and make no
  paid calls. A restored demo session must never invoke `LiveModels` after a mode switch.
- [x] Run `uv run pytest -q`, `uv run ruff check backend`, and `npm run eval:demo`.
  Expect all backend tests and all 16 existing scripted evaluations to pass without
  credentials. Commit: `feat: generate bounded validated plan sections with retained usage`.

### 1.5 Planning API and revision approval

Add the planning router with injected `Store`, `PlanningService`, session loader,
mode guard, and the existing per-session lock map. Do not create a second lock
registry inside the router.

| Method and route | Contract |
| --- | --- |
| `POST /api/sessions/{id}/plan` | Begin/resume an explicit attempt; SSE accepted sections and terminal result |
| `GET /api/sessions/{id}/plan` | Current state, accepted sections, pending sections, immutable revision/hash |
| `POST /api/sessions/{id}/plan/approve` | Exact plan ID/revision/hash/requirements revision; require `review_ready` |
| `GET /api/sessions/{id}/plan/bundle` | ZIP for the current approved hash; 409 for stale/draft/unapproved |

- [x] Add `backend/tests/test_planning_api.py`. Unknown session -> 404; blank or
  invalid body -> 422; mode mismatch, stale hash, concurrent conflicting work,
  unmet requirements, and invalid state -> 409. Retain redacted actionable model
  failure events; never send provider exception bodies or keys to the browser.
- [x] Emit bounded events `plan_started`, `plan_section`, `plan_ready`, and
  `plan_error`; each contains attempt identity, requirements revision, and
  accepted-section version. Final approval uses the completed content hash.
  GET reload is authoritative after missed events. Existing stream events continue
  working. Include planning availability and execution-disabled state in health.
- [x] Run `uv run pytest backend/tests/test_planning_api.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: expose planning progress approval and bundle endpoints`.

### 1.6 Progressive UI and phase-one acceptance

- [x] Add failing Vitest tests in `frontend/lib/planning.test.ts` for event
  revision matching, pending versus accepted sections, mode mismatch, error
  persistence, approval eligibility, and stale/corrected plan actions.
- [x] Add typed planning contracts and selectors in `frontend/lib/planning.ts`;
  reuse `frontend/lib/stream.ts`. Extend `Session` with planning state and `Health`
  with feature availability. Never infer approval from a view being open.
- [x] Add `PlanPanel`: separate human and engineering tabs over the same data,
  monospaced scrollable ASCII, cited decisions, proposed choices, unresolved
  questions, named pass progress, failures, usage, revision approval, and bundle
  export. Show that dispatch is unavailable until later delivery phases.
- [x] Wire a planning action after current requirements approval. Reload restores
  accepted sections and the active revision. Corrections clear active approval
  immediately. Buttons remain disabled for stale/partial/failed plans even when
  prior plan snapshots are inspectable. Keep the existing brief/build flow working.
- [x] Run `npm test`, `npm run typecheck`, `npm run build`, and `npm run eval:demo`.
  Do not build against an active dev server's `.next`; stop only an owned server.
  Run backend checks after shared API changes. Browser-check a demo: partial
  progress, synchronized views, approval, ZIP download, reload, and a correction.
  Commit: `feat: add progressive plan review and instruction bundle export UI`.
- [x] Present the generated fixture bundle and UI evidence for user review.
  Phase 1 acceptance requires complete consistent exports, visible unresolved
  choices, retained failure usage, and no execution path for partial/stale output.
  Stop before Phase 2 until the user accepts Phase 1.

## Phase 2: Codex transport and one work-package lifecycle

### 2.1 Version-qualified stdio protocol

- [x] Generate schemas from the installed CLI into ignored local storage:

```powershell
codex --version
codex app-server generate-json-schema --out .data/codex-schema
```

  Expect version output and schema files. Use these schemas to make a minimal,
  synthetic checked-in fixture subset; do not commit `.data/` or account reports.
  Requalify on CLI upgrades instead of assuming online examples match the binary.
- [x] Add `backend/tests/fixtures/codex/fake_server.py` and
  `backend/tests/test_codex_transport.py`. Drive a real local subprocess that
  simulates split JSONL chunks, out-of-order replies, notifications before a
  response, server requests, stderr noise, malformed/oversized frames, timeout,
  EOF, process death, cancellation, and shutdown of owned descendants on Windows.
- [x] Implement `codex/protocol.py` and `transport.py`: argv-based subprocess,
  independent stdout/stderr readers, bounded frames/logs/queues, request-ID futures,
  serialized writes, cleanup deadlines, and failure of all pending futures on
  connection loss. Requests use `id/method/params`; notifications omit `id`.
  Follow installed framing; do not prepend an unsupported JSON-RPC envelope field.
- [x] Initialize exactly once per connection, then send `initialized`:

```json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"intent","title":"Intent","version":"0.1.0"}}}
{"method":"initialized"}
```

- [x] Run `uv run pytest backend/tests/test_codex_transport.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: add version-qualified Codex app-server stdio transport`.

### 2.2 Account state, event routing, approvals, and reconciliation

- [x] Add `backend/tests/test_codex_client.py`. Test account missing/API-key/
  ChatGPT states, retained configured model, exact explicit model, unavailable
  model, supported approvals, denied/expired/unknown approvals, cross-thread event
  rejection, completed/failed/interrupted turns, account limits, and reconnect.
- [x] Implement the client with installed methods: `account/read`, `model/list`,
  `thread/start`, `thread/read`, `thread/resume`, `turn/start`, and `turn/interrupt`.
  Preserve the selected model; omit a model override when none is selected.
  Require the intended ChatGPT-backed account before subscription execution.
  Send only redacted account status to the UI; credentials remain Codex-managed.
- [x] Correlate every notification and server request to connection generation,
  thread, turn, item, and durable run. Persist permission requests with a deadline;
  forward them to the user and send only supported schema-valid decisions. Unknown
  permission methods block the run. Stale or duplicate replies never grant access.
- [x] Worker defaults use the installed supported workspace-write sandbox and
  user approval policy. No bypass flags. No model-created child workers. Sanitize
  child environment so Nebius keys, API billing overrides, and Intent secrets are
  not forwarded. Qualify inherited Codex settings/MCP tools against the intended
  execution policy before starting a worker; block unsupported policy combinations.
- [x] Reconnect reads known thread/turn state before resuming. An interrupted turn
  is not completed. Neither a lost response nor an empty thread read justifies an
  automatic replacement `turn/start`. Account refresh must not trigger sign-out,
  limit redemption, purchases, profile rotation, or billing-mode changes.
- [x] Run `uv run pytest backend/tests/test_codex_client.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: route Codex lifecycle events and user permission approvals`.

### 2.3 Durable single-package execution

- [x] Add `backend/tests/test_execution_store.py`, `test_codex_worker.py`,
  `test_execution_worktrees.py`, and `test_execution_api.py`. Cover crashes before/after external side effects,
  completed-turn replay, scope violations, cancellation, restart, and stale hash.
- [x] Persist run ID, package ID, plan/hash/requirements revision, account profile
  reference, configured model, worktree/base commit, connection generation,
  thread/turn IDs, dispatch intent, state, permission requests, and evidence in
  `execution/store.py`. Transactional claims must be unique for active package
  attempts. Explicit repair attempts have new IDs and retain old evidence.
- [x] Persist dispatch intent before `thread/start` and `turn/start`; persist
  returned IDs immediately. A crash between sending a request and saving its
  response is uncertain external state: block reconciliation, preserve its
  worktree, and never automatically create another worker for that attempt.
- [x] Add the initial `execution/worktrees.py` implementation before wiring the
  worker: validate app-owned roots, initialize an empty project with a local Git
  identity and initial commit, persist worktree ownership, and create one worktree
  using argv-based Git commands. Test creation, separate checkout identity, failed
  creation, and retained changes on cancellation. Phase 3 extends these invariants
  to multiple workers and adversarial filesystem cases.
- [x] Implement one worker using that app-owned Git root and separate worktree.
  Explicitly supply common rules plus the assigned packet as data; policy comes
  from Intent. Record worker-reported artifacts/tests/decisions as claims. A
  successful turn moves to `verifying`, never directly to `accepted`.
- [x] Add `POST /api/sessions/{id}/execution` with exact approved plan identity,
  `GET /api/sessions/{id}/execution`, `POST .../execution/{run_id}/cancel`, and
  `POST .../execution/{run_id}/approvals/{request_id}`. Server-side policy enforces
  the feature flag, current approval, model/account eligibility, and run ownership.
- [x] Run `uv run pytest -q` and `uv run ruff check backend`. Exercise one synthetic
  package with the fake server; no credentials required.
  Commit: `feat: persist and execute one Codex work package with safe recovery`.
- [x] Present fake-server lifecycle and restart evidence for Phase 2 review.
  Real-account smoke remains a separately labeled Phase 5 check.

## Phase 3: worktree isolation, scheduling, and integration

### 3.1 Owned Git roots and worktree lifecycle

- [x] Extend `backend/tests/test_execution_worktrees.py` using temporary real Git
  repositories. Cover empty initial project commits, independent worktrees,
  dirty/untracked files, conflicts, missing Git, symlinks/reparse points, and unsafe
  paths. Configure test identity locally within each temporary repository.
- [x] Harden `worktrees.py` with argv-based Git calls and validated app-owned
  roots. Persist ownership before creation and resolve every path under its root.
  Preserve failed/cancelled/stale worktrees; cleanup never discards unreviewed work.
  Never reuse or reset the Intent source checkout as a generated-project worktree.
- [x] Run `uv run pytest backend/tests/test_execution_worktrees.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: isolate generated-project workers in owned Git worktrees`.

### 3.2 Dependency scheduler and two-worker limit

- [x] Add `backend/tests/test_execution_scheduler.py`. Failing cases: dependent
  package before integration, ancestor/descendant path overlap, interface producer
  pending, two simultaneous dispatch claims, configured/global capacity limits,
  stale approvals, exhausted account allowance, and duplicate resume dispatch.
- [x] Implement deterministic selection by phase/package ID after prerequisites
  are integrated. Acquire transactional claims before launching; combine owned
  path and interface conflict checks with available capacity. One phase is active
  at a time. Never dispatch a successor phase from a worker completion callback.
- [x] Start with one worker, then enable two after tests pass. A failure stops new
  dispatch for the phase; interrupt affected active workers, preserve every patch,
  and require repair/review. Workers cannot recursively schedule more agents.
- [x] Run `uv run pytest backend/tests/test_execution_scheduler.py -q`,
  `uv run pytest -q`, and `uv run ruff check backend`.
  Commit: `feat: schedule dependency-safe Codex packages with bounded concurrency`.

### 3.3 Scope inspection, trusted checks, and controlled integration

- [x] Add `backend/tests/test_execution_verification.py`. Include renamed/deleted/
  untracked files, binary changes, symlink escapes, unexpected tracked artifacts,
  forged worker summaries, failing checks, stale base revisions, and merge conflicts.
- [x] Inspect actual Git changes against package ownership, exclusions, and
  protected instruction/control files. Treat worker-edited tests as changed code,
  not independent evidence. Verify approved acceptance artifacts and record their
  hashes. Out-of-scope changes block integration and remain available for review.
- [x] Package verification commands remain reviewable data. Run only a trusted,
  approved argv allowlist with explicit cwd, environment, output limits, deadlines,
  and sandbox policy. Never send model text through a shell or auto-install/run a
  generated project's arbitrary scripts outside the execution policy.
- [x] Collect exit codes, bounded redacted logs, artifact inventory, diff, actual
  changed paths, unresolved decisions, and command provenance. Integrate serially
  into an app-owned phase staging branch; block conflicts and rerun aggregate
  acceptance there. Only integrated prerequisites unblock dependent packages.
  Do not update the accepted project branch until user phase acceptance.
- [x] Run `uv run pytest -q` and `uv run ruff check backend`.
  Commit: `feat: verify scoped worker changes and stage phase integration`.
- [x] Present a fake two-worker phase with one dependency, one conflict case,
  and one out-of-scope failure.
- [x] Obtain user Phase 3 acceptance before Phase 4 (2026-10-27).

## Phase 4: evidence, phase review, corrections, and restart gates

### 4.1 Explicit state transitions and acceptance identity

- [x] Add `backend/tests/test_phase_review.py` and `test_execution_recovery.py`.
  Exercise every permitted transition and reject all other state pairs. Include
  stale-browser acceptance, rejected phase, incomplete checks, duplicate acceptance,
  correction during dispatch, limits, server restart, and an unknown active turn.
- [x] Implement `review.py` with distinct plan, run, and phase states. Plan:
  `draft -> planning -> review_ready -> approved`; correction -> `stale`.
  Package: `queued -> running -> verifying`; verified evidence contributes to phase
  review. Phase: `running -> verifying -> awaiting_phase_review -> accepted`.
  Failure/limit/uncertainty -> `blocked`; explicit cancel -> `cancelled`.
  Repairs create a new attempt and invalidate prior review evidence.
- [x] Define immutable `PhaseReview` identity from plan hash, phase ID, staging
  commit, package attempt IDs, check results/artifact hashes, and open decisions.
  Accept/reject requests include that identity. Reject stale evidence even when the
  plan hash is unchanged. Acceptance requires all required checks and artifacts,
  no unresolved blocking decisions, and a successful promotion of the reviewed
  staging commit. The scheduler also rechecks current requirements approval.
- [x] Add `POST /api/sessions/{id}/execution/phases/{phase_id}/review` with
  `decision: accept|reject`, plan identity, evidence hash, and optional review notes.
  Rejection preserves staging/worktrees and keeps successors blocked. Acceptance
  makes the next phase eligible but does not silently launch it.
- [x] Reconcile durable runs during lifespan startup before dispatch is enabled.
  Unlike the old HTML builder's restart recovery, an existing Codex thread must
  be inspected. Persisted `running` is not proof of an active or completed turn.
  Cancellation and correction remain effective when Codex interruption fails.
- [x] Run `uv run pytest -q` and `uv run ruff check backend`.
  Commit: `feat: require current phase evidence and explicit user acceptance`.

### 4.2 Execution UI and phase-four acceptance

- [x] Add `frontend/lib/execution.ts` and failing `execution.test.ts` selectors
  for phase eligibility, permission request identity, stale evidence, cancellation,
  account limits, restart uncertainty, and accepted-phase versus completed-turn state.
- [x] Add `ExecutionPanel` with worker/package progress, owned paths, bounded
  logs, model selection/default, account availability, permission requests, cancel,
  changed files/diff, trusted check results, artifact links, unresolved decisions,
  and accept/reject actions. Explain why the next phase is blocked. Show Codex
  usage separately from Nemotron estimated dollars and never invent a dollar cap.
- [x] Poll durable execution state; suppress stale responses by session/run/hash.
  Restore the panel after reload. Show an explicit next-phase start action only
  after acceptance. Corrections clear approval and dispatch eligibility at once.
- [x] Run `npm test`, `npm run typecheck`, `npm run build`,
  `uv run pytest -q`, `uv run ruff check backend`, and `npm run eval:demo`.
  Browser-check simulated permissions, cancellation, failed checks, reject/repair,
  acceptance, next-phase blocking, correction, and reload. Label simulation in UI.
  Commit: `feat: show Codex phase evidence permissions and user review gates`.
- [x] Present the simulated end-to-end review flow. Require Phase 4 acceptance
  before real generation qualification. No generated backend/deployment claim follows
  from source files or an HTML preview alone.

- [x] Obtain user Phase 4 acceptance before starting Phase 5 qualification (2026-10-27).

## Phase 5: real Nemotron and Codex qualification

### 5.1 Explicit qualification commands and redacted reports

- [x] Add offline tests for `backend/qualify_planning.py` and
  `backend/qualify_codex.py`. Reports must retain failure usage but exclude keys,
  auth payloads, transcript bodies, local account identifiers, and raw exceptions.
  Missing prerequisites produce explicit failed/incomplete reports without requests.
- [x] Implement module entry points with these exact CLI contracts:

```powershell
uv run python -m backend.qualify_planning --output .data/live-check/planning.json
uv run python -m backend.qualify_codex --output .data/live-check/codex.json
```

  Planning requires the server's own configured `NEBIUS_API_KEY`. Codex qualification
  checks its existing managed ChatGPT login and the explicit execution enable flag.
  Each command states before execution whether it makes provider/model requests.
  Never borrow credentials from another application or print secrets.
- [ ] Run existing `backend.smoke` checks separately; their pending status is not
  cleared by new planning tests. Run an actual live planning conversation, inspect
  both views and exported packets, and manually audit source fidelity, constraints,
  proposed choices, dependencies, scope, and screen states. Record per-pass usage,
  latency, selected models, requested controls, and observed provider results.
- [ ] Run a small real generated Git project through one package, then a phase
  with two independent packages. Verify actual changes, trusted check evidence,
  cancellation, reload/restart reconciliation, phase acceptance, and a correction.
  Keep all generated projects and reports ignored. One successful app is integration
  evidence, not a measured model-quality or general correctness claim.
- [x] Keep multiple-account concurrent inference explicitly unverified unless two
  distinct authenticated accounts are actually tested. The prior empty-profile
  isolation probe is supporting evidence only; account rotation is not a scheduler
  fallback. A single-account qualification is sufficient for initial local support.
- [x] Update `README.md` with dated, redacted results and exact remaining limits.
  Run relevant backend checks for qualifier code and `git diff --check` for docs.
  Commit qualifier code and tests as `test: add explicit planning and Codex qualification reports`;
  commit observed documentation separately as `docs: record planning and Codex qualification results`.
- [ ] Present actual evidence and remaining failures for Phase 5 acceptance.
  Missing credentials leave live qualification pending while preserving completed
  offline work. Never substitute fixture evidence for a live pass.

Phase 5 observed prerequisite checks (2026-10-27): the separate basic smoke and
planning commands exited 1 with `missing_credentials`; Codex exited 1 with
`execution_disabled`. There were zero model requests and no recorded usage.
No profile, sandbox or real generation pass is inferred. The new CLIs preserve
existing session allowances and approval gates. `--session-id` selects an existing
approved live session; `--phase-id` explicitly selects an execution phase. Existing
phase attempts are inspected without replay. Stop the app server before using
these direct-store commands. README documents the manual audit and interactive
permission flow. Overall reports remain incomplete pending that audit.

Checkpoint `e4e5973` adds the qualifier modules and 12 offline tests. Fresh full
verification: 229 backend tests passed, one Windows symlink test skipped and the
existing dependency warning remained. Ruff, 15 frontend tests, type checking,
production build and 16/16 demo evaluations passed. A dedicated demo-database
server started, served its health/session endpoints and shut down cleanly.

Live follow-up (2026-10-28): the server key authenticated; Nano, Super and Ultra
were listed by the provider. The basic live smoke passed after using existing OS
trust roots through a local `SSL_CERT_FILE` bundle, with certificate verification
enabled. Optional control probes produced mixed schema/grounding results and are
not qualified for enabling globally. A retained real counter conversation reached
all six confirmed slots and no readiness blockers after diagnostic re-extraction,
reanalysis and prompt/ranking fixes. Its corrected playback was manually audited;
human requirements approval is pending. No planning attempt, Ultra compilation,
export audit, Codex model turn, generated-phase review or Phase 5 acceptance has
occurred at this checkpoint.

The user explicitly enabled execution and signed in to a separate local Codex test
profile. That profile now qualifies on CLI 0.164.0 with `gpt-6.1-sol`, no inherited
MCP servers and no enabled skills; no credentials were copied. Effective generation,
sandbox and lifecycle behavior remain unverified. Raw artifacts and authentication
state remain ignored. Redacted evidence is under `.data/live-check/2026-10-28/`.

Local checkpoints: `eba9e0e` isolates offline tests from live developer settings
and blocks unmocked HTTP; `fc573aa` supplies ranking with ledger/history context
and refines model instructions. Verification: 234 backend tests passed, one
Windows symbolic-link test skipped, existing warning retained; Ruff, 15 frontend
tests, type checking, production build and 16/16 demo evaluations passed.

## Verification and requirement coverage

Phase 4 evidence (2026-10-27): 217 backend tests passed, one Windows symbolic-link
test skipped, and the existing Starlette/httpx warning remained. Ruff, 15 frontend
tests, TypeScript checking, the production build and 16/16 scripted demo evaluations
passed. `c93b6cf` adds immutable review identity, migration with retained attempt
history, acceptance/rejection, reviewed-commit promotion and startup reconciliation.
`a87f42d` adds the execution panel and selectors for current evidence and permissions.

Backend regressions cover same-plan stale staging/attempt/check evidence, duplicate
acceptance, rejection requiring fresh repair attempts, failed checks, correction,
lost promotion replies, moved refs, cancelled turns, legacy phase-three evidence
and unknown running turns. A two-phase fake-server test completes and accepts both
phases without rerunning prior packages. Successors pin their base to the preceding
reviewed commit even if the accepted ref moves externally.

Production-browser simulation covered permission decline, active cancellation,
failed checks, rejection and repair, acceptance, next-phase blocking, requirements
correction and reload. The restart uncertainty screen used an explicitly labeled
interrupted-dispatch fixture; actual history reconciliation used backend subprocess
tests. Desktop and mobile layouts were inspected. Observations and screenshots are
ignored under `.data/phase-four-check/`. All simulation remained local with zero
provider requests. Temporary servers and the browser tab were closed. The user
accepted Phase 4 on 2026-10-27; no Phase 5 qualification has started.

Phase 3 evidence (2026-10-27): 197 backend tests passed, with one symbolic-link test
skipped because Windows denied symbolic-link creation. Both Windows junction tests
passed, including an escape through Git object metadata. Ruff and all 16 scripted
demo evaluations passed. The existing Starlette/httpx deprecation warning remains.

A separate fake app-server simulation exercised two independent workers, a dependent
worker starting from its prerequisite's integrated commit, an integration conflict,
and an out-of-scope failure. Successful phases stopped at `awaiting_phase_review`;
failure cases remained blocked. Worktrees were preserved and accepted project trees
remained unchanged. Reports and generated repositories remain ignored under
`.data/phase-three-check/`. No provider requests or real account-backed generation
were made. The user accepted Phase 3 on 2026-10-27; Phase 4 follows below.

Checkpoints on `codex/phase-three`: `cfdecbf` hardens owned roots and separate
worktrees; `2de8de1` adds transactional scheduling and bounded concurrency;
`4534116` adds actual change inspection, artifact hashes, aggregate staging checks,
phase-start/verification APIs, durable integration intent and restart blocking.
Additional regressions cover shared interface readers, cancellation during
verification, changing artifact bytes, stale accepted bases, long Windows paths,
repository-defined Git filters and junctions inside Git metadata.

The initial trusted policy is deliberately restricted to `git-inspection-only-v1`:
only the exact proposed argv `["git", "diff", "--check"]` is supported. It resolves
to bounded, sanitized Git inspection of the saved base/snapshot. Other proposed
commands block until a separately qualified sandbox runner exists. Repository
filters, config overrides, unsafe links and external object stores are rejected;
checkout materialization reads raw blobs rather than executing filters. Worker
test edits and summaries remain changed code/claims. Textual exclusions and open
decisions are retained for review; Git inspection is not semantic or application
correctness evidence. Phase 4 adds explicit phase acceptance and accepted-ref promotion.

Phase 2 evidence (2026-10-27): 156 backend tests, Ruff, and 16/16 existing scripted
evaluations passed. A separate synthetic lifecycle run exercised artifact creation,
failed turns, lost `turn/start` replies, out-of-scope changes, permission approval,
and cancellation. All six runs preserved their owned worktrees. Successful turns
stopped at `verifying`; no phase was accepted and no dependency was dispatched.
Reports and generated projects remain ignored under `.data/phase-two-check/`.

Checkpoints: `79c72fc` stdio transport and Windows job ownership, `077e034` account,
policy, approvals and reconciliation client; `ea51ee4` adds
transactional claims, owned repositories/worktrees, API routes, cancellation,
correction invalidation, profile binding, observed token usage, and recovery.
The CLI schema was generated locally from 0.164.0. No real account-backed model
request was made. UI execution/permissions and integration remain later phases;
the Phase 2 API is disabled by default and requires a compatible signed-in profile.

Phase 1 evidence (2026-10-27): 109 backend tests, Ruff, 9 frontend tests,
TypeScript checking, production build, and 16/16 scripted evaluations passed.
Production-browser demo checks covered generation, both views and matching hashes,
approval, bundle download, reload restoration, and correction invalidation. Model
adapter tests used synthetic HTTP responses; no actual provider/model calls were
made. Runtime artifacts stay ignored under `.data/phase-one-check/`.
The final browser run also reapproved the corrected requirements, generated revision
2 within the two-attempt allowance, and exported 18 artifacts. Every artifact digest
and the exported canonical plan's content hash passed an independent readback check.

Local branch: `codex/phase-plans`, worktree `C:/Users/jiang/Intent-phase-plans`.
Checkpoints: `fb9724c` contracts/store, `e442e89` validation, `e823c63` render/export,
`c224425` generation, `08c6cab` API, and `82baf00` verification fixes. UI and final
evidence are recorded in subsequent commits on the same branch. No push or merge
is included. Fresh verification remains required for each future checkpoint.

| Design requirement | Implementation and proof |
| --- | --- |
| One versioned structure and synchronized prose/ASCII | 1.1-1.3 contracts, stable IDs, snapshot/hash/render tests |
| Progressive validated sections; no partial execution | 1.4-1.6 accepted-section SSE, failure and UI eligibility tests |
| Exact cited requirements, proposals, semantic fidelity | 1.2 coverage; 1.4 verifier rejection; 5.1 manual live audit |
| Bounded nesting, subplans, complete task packets | 1.1 contracts; 1.3 packet inventory and acceptance assertions |
| Export AGENTS.md/CLAUDE.md with safe paths/templates | 1.3 deterministic bundle and adversarial export tests |
| Existing budget and compiler policy remain explicit | 1.4 Super routing, session allowance, repair usage, compiler regression tests |
| Subscription-backed local Codex lifecycle | 2.1-2.3 installed schemas, fake server, account/mode gates; 5.1 actual run |
| Dependencies, worktrees, at most two workers | 3.1-3.2 real temporary Git fixtures and transactional dispatch tests |
| Scope inspection and deterministic evidence | 3.3 actual patch checks, trusted command provenance, staged integration |
| User review after every phase | 4.1-4.2 evidence identity, stale acceptance rejection, successor blocking |
| Correction/restart/limits/cancellation preserve work | 2.3 dispatch intents; 3.2 failure handling; 4.1 recovery tests |
| HTML preview limits and honest qualification | 4.2 UI boundaries; 5.1 separate offline/live reports and README |

## Protocol references and compatibility

The transport follows the [official Codex app-server documentation](https://learn.chatgpt.com/docs/app-server):
stdio initialization, threads/turns, streamed events, approvals, and interruption.
Treat generated schemas from CLI 0.164.0 as the initial wire-contract fixture source;
online protocol additions are not automatically supported by the installed binary.
The [authentication documentation](https://learn.chatgpt.com/docs/auth) distinguishes
ChatGPT-backed access from API-key billing. Intent must not switch between them.

This plan covers the local single-user application in the source design. Hosted
multi-user authentication, deployment, cross-device runtime support, and account
pooling need their own explicit designs and acceptance evidence.
