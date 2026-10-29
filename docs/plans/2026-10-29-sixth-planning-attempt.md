# Sixth live planning attempt

Goal: run exactly one sixth attempt using the verified outline repair correction.
Architecture: retain five failed attempts and all earlier grants; append one
`sixth_attempt` grant bound to their hashes, the consumed fifth grant, session and
approved requirements revision. The normal two-attempt policy and model/budget
limits remain unchanged. Stack: existing Python, Pydantic, SQLite and pytest.

Exact human authorization: "go ahead, do the sixth attempt". No seventh attempt,
plan approval, coding-agent dispatch, publication, merge or release is included.
Worktree: `C:/Users/jiang/.codex/worktrees/phase-four/intent`.
Branch: `codex/sixth-live-planning`, starting at `1168340`.

```text
Stopped server + fresh five-failure snapshot + exact human approval
  -> CAS save sixth grant -> CAS reserve revision 6 and consume grant
       valid plan -> immutable plan + both views -> human review
       failure/cancel/restart -> preserve evidence; no automatic replay
Changed snapshot / duplicate grant / attempt 7 -> reject before provider
Correction before reservation -> invalidate unused grant without refund
```

- [x] Add failing tests in `backend/tests/test_planning_sixth_attempt.py` for
  issuance, atomic reservation, history, failure/restart/correction, redaction,
  budget and refusal of ungranted sixth or any seventh attempt.
- [x] Add `PlanningSixthAttempt` in contracts and validate the previous grant and
  five attempt hashes. Extend shared allowance, session binding, invalidation,
  immutable persistence, reservation and local CLI `--sixth-attempt` together.
  Run focused tests, full `uv run pytest -q`, Ruff and demo smoke, inspect the diff,
  then commit the verified milestone. No model adapter or repair bound changes.
- [x] Save read-only preflight and exact approval privately under
  `.data/live-check/2026-10-29/attempt-6/`. Verify approved revision 3, five consumed
  attempts, three consumed grants, 66 usage records and the original brief. Issue
  one grant using the fresh state hash and verified implementation checkpoint.
- [x] Run the production qualifier once with the existing configured key/TLS
  trust bundle. Keep nine logical passes, one shared repair per pass, at most
  18 responses, 4096 output tokens per response and the existing $2 budget.
- [x] Audit the applicable outcome. On success, inspect full source coverage,
  both views, graph, fidelity and runner compatibility before human plan review.
  On failure, retain the exact boundary and diagnostics. Verify all prior evidence
  is unchanged and attempt 7 is refused before provider/save. Record the outcome
  in README and the current handoff, then commit documentation separately.

Baseline: the preceding implementation passed 459 backend tests, Ruff and all
16 scripted demos. The [fifth-attempt record](2026-10-29-fifth-planning-attempt.md)
explains the deterministic-outline repair correction at `219b1eb` and the retained
live failure. Runtime artifacts and credentials remain ignored.

Focused verification: 33 new sixth-attempt tests passed. An earlier combined run
passed 135 existing/new grant and outline-repair tests before the additional
sixth-specific cases were added. Ruff and whitespace checks passed; all 16 scripted
demos passed with zero provider calls. The full backend run passed 492 tests,
with one existing Windows symlink skip and one Starlette/httpx deprecation warning,
in 495.23 seconds.

Read-only preflight confirmed approved requirements/playback revision 3, five
retained failures, three consumed grants, 66 usage records, $0.13555108 cumulative
estimated spend and the unchanged $2 budget. The raw live state SHA matches the
fifth-attempt postflight. The operator server is stopped, credentials and TLS trust
are present. At that checkpoint, no sixth grant or live call had been issued.

Diff/security inspection covered session/revision binding, atomic issuance and
reservation, immutable history, local-only issuance, public audit redaction and
closed failure/restart/correction paths. No blocker was found. The change reuses
the existing grant, CLI, store and model adapter without a new retry mechanism.

## Observed sixth-attempt result

Checkpoint `b1ab901` implements the separate grant. The operator command issued it
against the fresh retained snapshot with the exact approval and full implementation
hash. One exclusive production qualifier invocation made three logical passes and
four Super responses: outline, screen, then two responses for the first phase.

The outline and one screen were accepted. The first phase's repaired response was
schema-valid but both packages had empty `exclusions`, omitting required constraint
L4, "No login, network, backend, or sync". Deterministic validation rejected it with
`Package misses scope exclusions`. The failed phase was not accepted or stored as
canonical content. Its existing repair had already been used for an initial
JSON/schema failure; the exact initial validation detail was not retained. No third
response was available or requested. No complete or approved plan was produced.

New usage: 16,309 input and 7,686 output tokens, estimated $0.01181010. Cumulative
usage is 70 responses and $0.14736118. All four grants are consumed. Read-only
postflight confirmed all five prior attempts, all three earlier grants, 66 prior
usage records, requirements/playback approval revision 3, compiled brief and
compiler count are unchanged. Attempt 7 is rejected before provider or save.
Private evidence is under `.data/live-check/2026-10-29/attempt-6/`.

## Offline section-validation follow-up

The earlier correction covered only outline validation. Screen and phase
deterministic checks still ran after schema acceptance, and the phase prompt's
"applicable constraints" wording understated the validator's requirement that
every package cite all confirmed constraint/non-goal IDs. No past response is
rewritten to make it pass.

The follow-up uses one Pydantic validator wrapper for outlines, screens and phases.
Screen source/state checks and phase citation, path, dependency, interface,
ownership and exclusion checks run within the existing two-response budget.
Final-phase acceptance also checks full requirement coverage before a section can
be accepted. Post-call validation and final semantic review remain as separate
guards. A schema error followed by a coverage error still fails after two responses;
the change does not add a repair or retroactively rescue attempt 6.

The phase prompt now explicitly requires `constraint_ledger_ids` in every
package's exclusions, including setup packages. Twenty mocked-HTTP regressions
cover repaired and repeated failures, source preservation, accepted-prefix retention,
final coverage and mixed schema/semantic failures without a third response. The
first new test failed at the expected boundary before implementation. All 89
focused section/outline/response/service/sixth-grant tests passed afterward.
Checkpoint `dfc707a` passed a fresh full backend run: 512 tests, one existing Windows
symlink skip and one Starlette/httpx deprecation warning, in 605.04 seconds. Ruff,
whitespace checks and all 16 scripted demos passed, with zero demo provider calls.
Diff/security inspection confirmed that checks remain application-owned and all
prior source, budget, response and approval gates are retained. Cleanup factors
the existing checks into one validator wrapper and one canonical phase validator;
no dependency or extra retry mechanism was introduced.

Read-only postflight confirms the stored sixth-attempt state remains byte-for-byte
unchanged during this offline correction. No seventh grant, request or coding-agent
dispatch was made. The correction has no live qualification evidence. The grant,
repair and documentation checkpoints remain local on `codex/sixth-live-planning`;
no push, PR, merge or release was requested or made. A complete plan and its view,
export, fidelity and runner audits remain pending.
