# Proposal: one recorded planning extension for Phase 5

Date: 2026-10-28 (America/New_York).
Status: approved by the human on 2026-10-28, implemented at `ec14afd`, and consumed
by one failed additional live attempt. No plan approval or fourth attempt is implied.

## Verified starting point

The retained counter session still has approved requirements revision 3, two
failed planning attempts, no accepted outline, no active plan, and no plan
approval. Read-only inspection found 59 usage records totaling an estimated
$0.11179258. Both attempts reserved only `planner:outline`. Local prerequisites
remain present: the session marker and database, provider key, OS trust bundle,
configured Codex profile directory, and execution opt-in. Profile presence is not
a fresh authentication or inference check.

Attempt 1 failed confirmed specification coverage after JSON repair. Attempt 2
covered all seven confirmed IDs but failed the ASCII diagram guard. Checkpoint
`a0af23f` exposed the ASCII rule in the provider schema so the existing single
repair can address it. That fix has offline evidence and no live pass.

The current product intentionally blocks a third attempt in several places:

| Location | Current rule |
| --- | --- |
| `backend/app/settings.py`, `Settings.planning_max_attempts` | Default 2; maximum 2 |
| `backend/app/planning/contracts.py`, `PlanningState.attempts` | At most 2 stored attempts |
| `backend/app/planning/service.py`, `PlanningService.generate` | Reject at the configured attempt limit before reserving a pass |
| `backend/app/planning/routes.py`, generation/detail endpoints | Enforce and display the same configured limit |
| Original five-phase plan, proposed defaults | Failures and corrections consume allowance; restore does not replenish it |

The dollar budget has room. The planning allowance, rather than API credits,
blocks progress. Raising an environment variable alone is unsupported. Editing
counters, replacing the session, or invoking the model outside the service would
evade the agreed policy.

## Proposed decision

Authorize implementing and using **one additional planning attempt for this
retained session and its approved requirements revision 3**. Preserve the normal
two-attempt policy for every session without an explicit recorded extension.
The human approved this product-policy amendment after reviewing the proposal:
"yes, I approve the using one extra attempt proposal. make sure all the smoke tests and test pass"
The earlier request to resume verification alone did not approve it.

The extension would have these bounds:

- Keep both failed attempts, their errors, reserved passes, and all usage intact.
  Append attempt revision 3 under the existing plan identity.
- Persist one extension record in the session, including its unique identity,
  requirements revision, the two prior attempt identities, timestamp, reason,
  implementation checkpoint, and the explicit approval text. It grants exactly
  one attempt and cannot be renewed or multiplied.
- Issue it through an explicit local operator command while the app server is
  stopped. Provide a read-only preflight before issuance. No browser grant API
  or environment-wide increase is proposed. Issuance rechecks the saved state
  atomically and rejects changed requirements, attempts, or approvals.
- Keep the ordinary settings maximum at two. Expand storage capacity to three
  only with a valid extension record for the third attempt. Share one effective
  allowance calculation between service guards and API detail/preflight.
- Bind dispatch to the approved requirements and prior attempts recorded in the
  extension. A correction invalidates an unused extension; it never replenishes
  a consumed one. Retain its audit record after invalidation or consumption.
- Allow at most nine logical passes in attempt 3, each with at most the existing
  single JSON repair: at most 18 additional provider responses. Existing session
  dollar-budget checks still apply. Failure, interruption, or restart consumes
  the attempt once reserved; no automatic retry follows.
- Keep coverage, citations, diagram rules, semantic verification, and all plan
  and execution approval gates unchanged. A successful attempt stops at plan
  review. It does not authorize plan approval or generated execution.

If the additional attempt fails, stop with the preserved diagnostics. Any later
policy change needs a new decision; this proposal provides no fourth attempt.

## Implementation and verification after approval

1. Add the bounded extension contract and backward-compatible session loading.
   Centralize effective allowance checks; make storage reject an ungranted third
   attempt. Retain valid historical attempts after correction and restart.
2. Add the local preflight/issuance command with atomic compare-and-save checks.
   Repeated issuance returns the existing grant or rejects a mismatch; it cannot
   create another allowance. Reports exclude session IDs, approval bodies, keys,
   account details, and transcript content; full audit state stays ignored.
3. Add offline regressions before implementation: default exhaustion; valid third
   attempt; rejected fourth attempt; stale/duplicate grant; correction; restart;
   concurrent issuance/generation; usage preservation; JSON repair/pass bounds;
   semantic rejection; API limit consistency; and separate plan approval.
4. Run `uv run pytest -q` and `uv run ruff check backend`. If frontend behavior
   changes are needed, first read its instructions and installed Next.js guides,
   then run `npm test`, `npm run typecheck`, and `npm run build`. Commit verified
   implementation separately from observed live evidence.
5. Issue the approved extension against the retained session, then use the normal
   planning service with the configured key and verified OS trust bundle. Record
   per-pass latency, usage, selected models, and failures without leaking secrets.
6. If planning succeeds, render both actual views, audit provenance, proposals,
   dependencies, paths, screen states, and trusted-check compatibility. Present
   the exact plan identity for separate human approval before export/execution.

## Alternative

Keep the existing policy. Phase 5 remains incomplete with honest failed live
planning evidence; generated execution cannot start. No session reset or cloned
replacement is needed for either decision.

## Resume verification evidence

On 2026-10-28, the resume audit ran the handoff's focused command: 32 tests passed
in 9.16 seconds across `test_plan_contracts.py`, `test_models.py`, and
`test_planning_service.py`. Another 18 persistence/API/qualification tests passed
in 46.80 seconds across `test_plan_store.py`, `test_planning_api.py`, and
`test_qualification.py`, with the existing Starlette/httpx deprecation warning.
`uv run ruff check backend` passed. No provider or Codex model request was made,
and no runtime session state was changed. This documentation checkpoint does not
claim a fresh full-suite or live qualification pass.

## Approved implementation verification

The implementation adds the bounded extension and operator command described
above, with 33 extension regressions. A separate delayed-start regression fixes
the transport test fixture's startup/fault-deadline coupling; production transport
deadlines are unchanged. Three existing planning fixtures now save their changed
inputs before generation, matching the production snapshot/concurrency boundary.

Fresh full verification on 2026-10-28: 276 backend tests passed, one Windows symlink
test was skipped for the existing permissions limitation, and the existing
Starlette/httpx warning remained. Ruff, 15 frontend tests, type checking, production
build, and all 16 labeled demo evaluations passed. A built-app HTTP/proxy smoke
passed streamed demo planning, both views, and the export approval gate; its
owned servers were stopped.

The first basic live smoke failed with generic Nano `model_error`; the report
did not preserve its precise cause. An instrumented repeat passed Nano, Lightning,
and Super with unchanged runtime/prompts. The optional thinking-controls smoke
also passed; historical failures remain recorded and the default stays off.
The isolated Codex profile qualified without inference; its overall qualification
report remains incomplete pending an approved plan and generated execution.
These results do not yet establish a successful third planning attempt.

## Observed third-attempt outcome

After the final checks and code checkpoints, the local operator command recorded
the exact approval, approved revision 3, the two prior attempt hashes, and full
implementation commit. The production qualifier then ran exactly one added attempt.
The outline covered all seven confirmed IDs and passed ASCII constraints; one
screen was accepted. The first phase used its existing single JSON repair, then
returned schema-valid `ui-setup-phase` instead of the outline's `ui-setup`.
Application validation correctly blocked it. No phase or immutable plan was accepted.

There were three logical passes and four Super responses, costing an estimated
$0.01263540. Cumulative retained usage is 63 responses and $0.12442798 estimated.
The approved brief, requirements revision, prior attempts, and prior usage were
unchanged. The rejected phase also included shell-style checks and a placeholder
verification command incompatible with `git-inspection-only-v1`; none was executed.
Changing its ref alone would not qualify its fidelity or checks.

The extension is consumed and all three attempts are exhausted. Read-only
postflight confirmed rejection before a provider call or a store save.
No fourth attempt was made. No plan approval, bundle, Codex inference, or
Phase 5 acceptance followed. The latest basic/controls probes and all offline
checks passed; overall live planning remains failed/incomplete. Saved outcomes,
validated candidates, before-snapshot, and the failure audit remain ignored under
`.data/live-check/2026-10-28/extension-attempt-3/`.
