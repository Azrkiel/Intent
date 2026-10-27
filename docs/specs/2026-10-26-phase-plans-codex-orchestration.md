# Draft: visual phase plans and Codex orchestration

Status: revised design with a file-level implementation plan for review; no runtime
implementation is included.
Date: 2026-10-26 (America/New_York).

Next artifact: [implementation plan](../plans/2026-10-26-phase-plans-codex-orchestration.md),
covering bounded planning passes, repository ownership, tests, small commits and
user acceptance gates for all five delivery phases. Runtime implementation has not
started; the first checkpoint is planning contracts and persistence.

## Goal

Turn clarified intent into a coherent design and a dependency-aware implementation
plan, export detailed agent work packages, and optionally execute those packages
through the user's local Codex installation. The user reviews each completed phase
before the next phase can start.

This supersedes the proposed one-command Claude-to-Codex replacement. It does not
mark the pending live Nemotron qualification as complete.

## User requirements

The design responds to these requests from the current conversation:

- "nemotron to draw out the plan with ascii as it makes the plan"
- "one plan with straight words and shows a wireframe with the implmenetation"
- "a second one, nemotron will draw out an ascii plan with exactly what needs to be done and how"
- "creating independent sections for the codex agent to work on"
- "the independent sections will have plans for it's subplan to be worked on too"
- "generate phase plans with claude.md agents.md, etc that gives verbose instructions"
- "directly orchestrate agents through calling openAI's subscription model"
- "Review each completed phase before starting the next (Recommended)"

## Design choice: one structured plan, multiple views

Nemotron proposes a structured plan. Intent validates and persists it, then renders
both requested views from the same revision. Two separately authored plans could
disagree about decisions, dependencies or completion; they must not become separate
sources of truth.

The human view explains the vision, user journeys, scope, proposed implementation
choices and acceptance criteria. It includes ASCII wireframes for screens, with
empty, loading, error and success states where relevant. Technology or UX choices
not specified by the user are marked as proposals rather than confirmed requirements.

The engineering view contains architecture/data-flow diagrams, a dependency graph,
phase ordering and task details. Every task specifies what to change, why, its
inputs/outputs, owned files, dependencies and verification. ASCII complements these
details; diagrams alone cannot express an executable implementation contract.

```text
[User prompt -> clarification -> quoted intent ledger]
                         |
                         v
              [Approved, cited requirements]
                         |
                         v
           [Nemotron outline and phase proposals]
                         |
            invalid -----+----> [Show failure; retain usage; execution blocked]
                         |
                       valid
                         v
             [One versioned structured plan]
                  /                  \
                 v                    v
       [Human design view]    [Engineering view]
       prose + wireframes     ASCII + phase/task graph
                  \                  /
                   v                v
                [Review and approve this revision]
                         |
                  +------+------+
                  v             v
             [Export bundle] [Run eligible phase]
```

## Progressive diagrams

The UI updates as complete outline, screen and phase sections pass validation.
Each accepted section updates the prose and diagram views together. Partial JSON,
incomplete tasks and unvalidated edges remain draft output and cannot be executed.
An initial skeleton can show pending phase details without pretending those details
already exist. Users can inspect a phase while the remaining phases are prepared.

Intent owns stable plan, phase and task IDs and resolves proposal references.
The application checks referenced ledger IDs, requirement coverage, dependency
existence, cycles, task ownership conflicts and bounded nesting. Nemotron never
replaces the intent ledger or determines readiness on its own. Semantic verification
is still required; a well-formed plan is not proof of faithfulness.

Planning is an explicit additional stage after requirements approval. It must have
bounded named passes and use the existing session spend accounting. It must not
silently reset the session budget or bypass the existing compiler-call policy.
The implementation plan must specify any deliberate change to those limits.

## Phase and task contracts

A phase contains one or more work packages. A work package contains leaf tasks or
one bounded subplan. Initial nesting is limited to phase -> work package -> leaf
task; there is no unbounded recursive delegation.

Each work package contains:

- Goal, relevant user decisions and source ledger IDs.
- Preconditions, prerequisite artifacts and dependency IDs.
- Explicit owned paths and shared interfaces it consumes or produces.
- Ordered implementation steps and an ASCII flow of happy and failure paths.
- Acceptance criteria, verification commands and expected observable results.
- Scope exclusions, proposed choices and unresolved questions.
- Required output artifacts and the evidence needed to call the task complete.

Dependencies determine independence. Work packages can run together only after
their prerequisites are integrated and their owned files/interfaces do not conflict.
For example, agree shared API contracts before dispatching dependent UI and API
work. A model's assertion that two tasks are independent is insufficient.

```text
[P1: shared contracts]
          |
     tests + review
          |
     user accepts
          |
          v
[P2: implementation]
     |             |
     v             v
 [UI package]  [API package]   <- concurrent only with compatible ownership
     |             |
     +------+------+
            |
      integrate + test
            |
       user accepts
            |
            v
[P3: end-to-end acceptance]
```

## Exported instruction bundle

An export is useful independently of the executor. Its contents are generated from
one approved plan revision and carry that revision/hash in a manifest.

```text
project-plan/
  plan.json                    canonical structured plan and provenance
  manifest.json                revision, hashes and artifact inventory
  VISION.md                    purpose, user journeys and scope
  SPEC.md                      cited requirements and proposed choices
  WIREFRAMES.txt                proposed screens and states
  ARCHITECTURE.txt              data flow and dependency diagrams
  AGENTS.md                    common execution and verification rules
  CLAUDE.md                    compatibility entry point referencing shared rules
  phases/
    P1/
      PLAN.md                  phase goal, dependencies and completion gate
      DIAGRAM.txt              phase flow and failure paths
      work-packages/
        W1/
          TASK.md              full assigned task/subplan and acceptance checks
          CONTEXT.md           relevant decisions and dependency outputs
    P2/
      ...                      same generated structure for each actual phase
```

Workers are explicitly given their assigned task packet and the common rules.
Putting instructions under `phases/` does not automatically apply scoped AGENTS.md
rules to source code in another directory. Scoped instruction files, when needed,
must follow the generated project's actual directory structure.

Agent instructions come from application-controlled templates with validated plan
fields. Quoted user content remains product data; it cannot grant tool permissions,
change the sandbox or override execution policy. Export paths and archive members
are checked for traversal and collisions. Exports contain no credentials or sessions.

## Execution: local Codex app-server

For the current local, single-user Intent app, use the documented Codex app-server
integration over stdio. It provides thread/turn lifecycle, streamed progress,
approval requests and interruption. A JSON-RPC client and scheduler replace the
Claude-specific stream parser; the app does not scrape tokens or invent a private
subscription API.

Use the supported ChatGPT sign-in path for subscription-backed Codex access. Respect
account/workspace permissions and available models. Preserve the user's selected
model, or the configured default when none was chosen. Authentication remains in
Codex-managed storage and never enters exported plans or browser payloads.

Intent owns scheduling rather than allowing workers to create unlimited child
agents. Each work package receives a separate thread and Git worktree. Start with
at most two concurrent workers. Workers report artifacts, changed paths, tests,
unresolved decisions and a completion summary; self-reported success is not the gate.

```text
[Approved phase + current plan hash]
                 |
                 v
   [Intent scheduler checks dependencies]
                 |
          +------+------+
          v             v
    [Codex worker A] [Codex worker B]
    own worktree     own worktree
          |             |
          +------+------+
                 |
      [Inspect changes + run checks]
                 |
         fail ---+----> [Blocked; fix/review; preserve work]
                 |
                pass
                 v
       [Assemble phase review result]
       diff + test evidence + open decisions
                 |
                 v
        [Await user phase acceptance]
                 |
       rejected -+----> [Revise current phase]
                 |
              accepted
                 v
           [Next phase eligible]
```

User review is required after every completed phase. Internal task completion never
starts the next phase automatically. A review thread may assist, but deterministic
checks and user acceptance remain distinct gates.

Persist task IDs, worktree paths, thread/turn IDs, run state, approval revision and
verification evidence. A reconnect checks the existing run before retrying; it
does not blindly launch another worker. A completed turn, produced files or passing
tests alone cannot prove that the whole phase meets its acceptance criteria.

Initial states are draft, planning, review_ready, approved, queued, running,
verifying, awaiting_phase_review, accepted, blocked, cancelled and stale. State
transitions are orchestrator-owned. A correction creates a new plan revision,
invalidates approval for dependent work, stops new dispatch and requests interruption
of affected active workers. Existing changes are preserved for review rather than
silently discarded or integrated into a different revision.

Execution has sandbox policies, deadlines, concurrency limits, cancellation and
visible usage. Subscription allowance is not unlimited and token counts are not an
exact dollar cap. Reaching a limit blocks further dispatch; the app never redeems
resets, buys credits or switches billing methods automatically.

Generated output may be a project repository, not just one HTML file. However,
Intent's existing embedded preview remains HTML-only. Creating backend source does
not establish backend execution, deployment or cross-device sync; those claims need
an explicit runtime and functional acceptance evidence.

## Alternatives considered

1. Export only: smallest initial slice and works with multiple coding tools, but
   users must coordinate runs manually.
2. Codex exec subprocess per task: straightforward automation, but a thinner
   interface for interactive approvals, steering and recovery.
3. Export plus local app-server orchestration: recommended target for this request;
   it supports the desired in-product phase review and agent lifecycle. Deliver
   export first, then the transport and scheduler as independently verified slices.

## Delivery order and acceptance

1. Structured planning contracts, validation, incremental views and export. Offline
   fixture tests must prove prose, diagrams and work packets share the same IDs and
   revision, all confirmed requirements are covered, and unresolved choices remain
   visible. Failed/partial planning cannot enable execution.
2. Codex app-server transport and a single work-package lifecycle. Test initialization,
   authentication status, event routing, approval forwarding, failure, cancellation
   and reconnect using a fake server before a real account-backed smoke check.
3. Dependency scheduling and worktree isolation, then two-worker execution. Tests
   must prove dependent/conflicting tasks are not dispatched concurrently, completed
   tasks are not duplicated on resume, and out-of-scope changes block integration.
4. Phase evidence and user review gates. The next phase must remain blocked until
   acceptance of the current revision. Corrections, failures, limits and server
   restarts must preserve work while preventing stale dispatch.
5. Real Nemotron planning and real Codex execution qualification. The existing
   missing Nebius key still blocks actual Nemotron evidence; simulation stays
   labeled. A Codex login is independent of that key.

The linked implementation plan maps these slices to repository files, bounded
model passes, tests and small commits. Its checklist records pending work, not
implementation or qualification evidence.

## Account-isolation probe (2026-10-26)

With installed Codex CLI 0.164.0, three local app-server processes initialized and
answered account-state requests concurrently: the existing ChatGPT login and two
new, empty profiles with separate state directories and file-backed credential
storage. Neither empty profile inherited the primary login. Signing out of one
empty profile left the primary account state unchanged, and the primary auth file
was unchanged. The probe made no model requests and stopped its owned processes.

A second-account sign-in was opened, then cancelled because the user did not have
a second account available. Two authenticated accounts and concurrent inference
under different accounts remain untested. The successful isolation probe must not
be reported as proof of that stronger capability. Redacted reports and diagnostic
scripts remain local under the ignored `.data/multi-account-check/` directory.

## Official integration references and limits

- [Codex authentication](https://learn.chatgpt.com/docs/auth): ChatGPT sign-in
  provides subscription access; API-key sign-in provides usage-based access.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server): local protocol,
  authentication, thread/turn lifecycle, approval handling and usage information.
  The command/protocol is experimental; qualify against the installed CLI schema.
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode):
  alternative subprocess integration and JSONL event stream.
- [Sign in with ChatGPT app-server integration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server):
  the separately documented route for application-managed ChatGPT plan access.

The recommended first integration is the current local/open-source app. If Intent
becomes a hosted or commercial product, use the applicable Sign in with ChatGPT
integration and eligibility requirements; a local app-server login is not assumed
to authorize a hosted multi-user service.
