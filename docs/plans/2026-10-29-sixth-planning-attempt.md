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
- [ ] Save read-only preflight and exact approval privately under
  `.data/live-check/2026-10-29/attempt-6/`. Verify approved revision 3, five consumed
  attempts, three consumed grants, 66 usage records and the original brief. Issue
  one grant using the fresh state hash and verified implementation checkpoint.
- [ ] Run the production qualifier once with the existing configured key/TLS
  trust bundle. Keep nine logical passes, one shared repair per pass, at most
  18 responses, 4096 output tokens per response and the existing $2 budget.
- [ ] Audit the applicable outcome. On success, inspect full source coverage,
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
are present, and no sixth grant or live call has been issued yet.

Diff/security inspection covered session/revision binding, atomic issuance and
reservation, immutable history, local-only issuance, public audit redaction and
closed failure/restart/correction paths. No blocker was found. The change reuses
the existing grant, CLI, store and model adapter without a new retry mechanism.
