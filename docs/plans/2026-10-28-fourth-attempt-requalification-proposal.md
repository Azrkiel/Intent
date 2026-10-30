# Proposal: one further live qualification attempt after request-contract fixes

Date: 2026-10-28 (America/New_York).
Status: approved by the human on 2026-10-28, implemented at `af20dea`, and consumed
by one failed fourth live attempt. No fifth attempt or generated-plan approval follows.

The approval turn was exactly: "yea, that's fine". It followed the explanation that
this is one new Nemotron planning attempt under the existing budget, stops on
success/failure, and does not start Codex/Claude or approve the generated plan.
Do not ask for this same policy approval again.

## Approved decision

Authorize implementing and consuming one new, separately audited qualification
grant for the retained counter session and its already approved requirements
revision 3. The grant would permit attempt revision 4 under the same plan identity.
The ordinary two-attempt limit and the previously consumed third-attempt extension
would remain unchanged. This is a product-policy amendment, not an environment
setting or an instruction to rerun the existing qualifier immediately.

The alternative is to retain the current policy and leave live Phase 5 incomplete.
The offline fixes can be kept under either decision.

## Why another decision is necessary

The earlier proposal authorized exactly one third attempt and explicitly said that
failure requires a new policy decision. That attempt failed. The request to continue
the handoff authorizes investigation and offline fixes; it does not explicitly
amend the exhausted allowance. No session reset, clone, replacement approval,
out-of-service provider call, or replay of the rejected phase is appropriate.

Read-only inspection of the retained session confirmed approved revision 3,
three consumed attempts, a consumed extension, 63 usage records, an estimated
cumulative spend of $0.12442798, and no active plan or plan approval. The production
generation guard still rejects the session before accessing a store or provider.
The dollar budget is not the exhausted resource.

## Offline diagnosis and changes

The third attempt returned `ui-setup-phase` where the accepted outline declared
`ui-setup`. Previously, the general phase schema accepted either string. The
application caught the mismatch only after the model adapter had completed its
single JSON-repair opportunity. Screen references had the same gap.

Each screen/phase request now supplies a schema that requires its exact accepted
reference. The existing adapter can therefore repair that validation failure
within its existing two-response bound. Two invalid responses still block planning;
the application never renames or silently repairs the returned reference.

The rejected candidate also proposed shell-style and placeholder checks that the
executor cannot run. When Codex execution is enabled, phase requests now receive
the actual `git-inspection-only-v1` policy and allowed argv from the executor's
constants. The prompt distinguishes whitespace inspection from behavioral
verification and prohibits unsupported runners and placeholder expectations.
The existing context preflight remains authoritative. Prompting is not a guarantee
of compatible commands, faithful output, or a successful new live attempt.

Six offline regressions cover repaired and repeated reference mismatches for both
section kinds, retained usage, one reserved logical pass, withheld approval,
blocked downstream verification, and policy context enabled/disabled. They use
the real model adapter with a simulated HTTP transport and make no provider calls.
Checkpoint `228c518` contains these fixes. Fresh verification passed 340 backend
tests with one existing Windows symlink skip and one existing dependency warning,
Ruff, and all 16 labeled demo evaluations. The full suite took 464.26 seconds.
No frontend files changed. Before/after hashes of the retained live session match;
no provider or Codex model request, new approval, or execution occurred.

## Approved implementation scope

1. Add a separate qualification-grant record; do not modify, replace, or replenish
   the original extension. Bind it to the retained session, approved requirements
   revision, hashes of all three prior attempts, consumed extension identity/hash,
   exact recorded human approval, reason, timestamp, and implementation commit.
   Allow only one such grant, with granted/consumed/invalidated lifecycle states.
2. Add an explicit local read-only preflight and issuance path while the app server
   is stopped. Use an atomic state-hash comparison, current approval/readiness,
   three failed attempts, no active plan/plan approval, and the consumed original
   extension as prerequisites. Duplicate/concurrent issuance cannot add allowance.
3. Update `PlanningState`, the shared effective-limit calculation, generation,
   store preservation rules, and operator reporting together. A valid new grant
   permits only attempt 4; all other sessions keep their existing limits. Retain
   attempts 1-3, their errors, accepted partial sections, and all usage unchanged.
   The consumed original extension must remain valid with four retained attempts.
   Hide the new private approval/session metadata from public API representations.
4. Consume the new grant atomically when attempt 4 is reserved. A correction
   invalidates an unused grant without returning consumed allowance. Restart,
   cancellation, failure, or repeated issuance never supplies another attempt.
   Attempt 5 remains unsupported. Existing JSON repair, section limits, semantic
   validation, source checks, and the session dollar budget remain unchanged.
5. Test default exhaustion, valid fourth attempt, refused fifth attempt, unchanged
   historical records, stale/duplicate/concurrent issuance, correction/restart,
   consumption before dispatch, public redaction, store rollback, and separate
   plan approval. Run the full backend suite, Ruff, and labeled demo evaluation
   before committing. Run frontend checks if any frontend behavior changes.
6. After the implementation is verified, record the actual human approval and issue
   exactly one grant against a fresh retained-session snapshot. Use the normal
   production planning service, existing provider configuration, and verified OS
   trust bundle. Respect the configured maximum of at most nine logical passes
   with one repair each: at most 18 provider responses, within the existing budget.
7. Stop after success or failure. On failure, preserve diagnostics and consumed
   allowance; do not automatically retry. On success, inspect the actual plan,
   both text views, graph, citations, owned paths, interfaces, checks, exports,
   and per-pass usage. Present the exact immutable plan for separate human
   approval. This proposal does not approve a model-produced plan, its worker
   contexts, Codex dispatch, phase acceptance, or overall Phase 5 acceptance.

Expected implementation files are `backend/app/planning/{contracts,allowance,service}.py`,
`backend/app/store.py`, the local extension/operator command, and their tests.
The implementation adds the separate grant and `--requalify` operator mode;
verification and observed live results are recorded below and in the current handoff.

## Implementation verification and observed outcome

Checkpoint `af20dea` adds the separate `PlanningRequalification`, shared allowance,
atomic reservation, original-extension/history bindings, correction invalidation,
store preservation, private API exclusions, and explicit operator `--requalify` mode.
Its 37 regressions cover default exhaustion, valid fourth/refused fifth attempts,
concurrent issuance/generation, stale state, database rollback, immutable history,
correction/restart, budget/pass bounds, real-adapter single repair, and redaction.

Fresh verification passed **377 backend tests**, one existing Windows symlink skip,
and one existing Starlette/httpx warning in 380.89 seconds; Ruff, diff whitespace,
and all 16 labeled demo evaluations passed. No frontend source changed.

After verification and the code commit, the operator recorded the exact approved
turn against the retained session and implementation commit. The original extension,
attempts 1-3, and 63 prior usage records were preserved. One guarded production
qualification attempt then ran with the existing key and OS trust bundle; no
credential or account configuration was changed.

The fourth attempt reserved only `planner:outline` and **failed after one repair**.
Its final diagnostic was `string_pattern_mismatch` at `architecture`: the repaired
diagram did not satisfy the ASCII schema. The first response used 4096 output tokens;
raw output and finish reason were not saved, so truncation is not established.
No outline, immutable plan, plan approval, bundle, or Codex turn was produced.

Exactly two Super responses cost an estimated **$0.00818940**. The retained session
now has 65 usage records and estimated cumulative spend **$0.13261738**. Both grants
are consumed; approved requirements revision 3, the compiled brief, historical
attempts, and prior usage are unchanged. Postflight confirmed the 4/4 limit and
rejection of attempt 5 before a provider call or save. There is no automatic retry.

Private evidence is ignored under `.data/live-check/2026-10-28/requalification-attempt-4/`.
The driver must not be rerun. Further work can investigate diagram reliability
offline; any later live allowance needs a new explicit policy decision. Overall
live planning and Phase 5 remain failed/incomplete.

## Remaining qualifications

- The exported graph viewer's real from-disk opening with networking disabled
  remains unverified. The earlier browser URL-policy rejection must not be bypassed.
- No live plan or Codex model turn has succeeded for the retained session. A profile
  read or a simulated test does not establish authenticated execution behavior.
- The executor's trusted command checks whitespace only. Behavioral acceptance
  still needs actual inspection; arbitrary generated scripts/tests are not authorized.
- Multiple-account and mixed Claude/Codex scheduling remain outside this proposal.

References: [original consumed extension](2026-10-28-planning-requalification-proposal.md),
[five-phase plan](2026-10-26-phase-plans-codex-orchestration.md),
current handoff (session handoff 2026-10-28-0843, not retained).
