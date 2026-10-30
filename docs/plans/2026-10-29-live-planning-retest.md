# One audited live planning retest

Goal: qualify the merged section-validation repair with one seventh attempt on
the retained, requirements-approved live session.

Architecture: append a `PlanningSeventhAttempt` grant bound to the consumed sixth
grant and all six prior attempt hashes. Reserve revision 7 and consume the grant
in the existing compare-and-swap transaction. Preserve the default two-attempt
policy, nine logical passes, one shared repair per pass, 4096 output tokens per
response, and the existing cumulative $2 session budget. Attempt 8 stays closed.
Stack: Python, Pydantic, SQLite, existing Nemotron adapter, pytest.

The user approved the proposed bounded retest with "yes, go ahead please" after
being told that the previous allowance was exhausted. Preserve that quote and its
context privately. Approval covers this retest; it does not approve an unseen
generated plan or waive context and worker approval gates. No automatic retry,
public deployment, or additional planning allowance is included.

```text
Merged main + six failed attempts + current approved requirements
  -> read-only preflight + backup + exact approval + implementation commit
  -> CAS issue seventh grant -> CAS consume grant and reserve attempt 7
       valid complete plan -> views + graph + fidelity/runner audit -> human review
       failed/interrupted -> retained prefix + usage + diagnostics -> stop
Changed snapshot / duplicate issuance / attempt 8 -> reject before provider/save
Correction -> invalidate unused grant; keep all history and usage
```

Files and ownership:

- `backend/app/planning/contracts.py`: seventh grant and history validation.
- `backend/app/planning/allowance.py`: effective limit shared with the API.
- `backend/app/planning/service.py`: consume the grant during atomic reservation.
- `backend/app/{domain,engine,store}.py`: binding, redaction, invalidation and
  immutable grant/history persistence.
- `backend/planning_extension.py`: local-only `--seventh-attempt` preflight and
  issuance with fresh state hash, approval file, reason and commit.
- `backend/tests/test_planning_seventh_attempt.py`: history, CAS, budget,
  interruption, redaction, API injection and replay regressions.
- `.data/live-check/2026-10-29/attempt-7/`: ignored private evidence only.

- [x] Write the regressions first; run
  `uv run pytest backend/tests/test_planning_seventh_attempt.py -q` and confirm
  rejection because the seventh-attempt operator option does not exist.
- [x] Implement the existing grant pattern. Run all grant/section-repair tests,
  `uv run pytest -q`, `uv run ruff check backend`, and the demo evaluations.
  Review binding, redaction, immutable history and retry bounds; commit the
  verified implementation before any provider request.
- [x] Capture a fresh read-only preflight, SQLite backup and private approval.
  Stop the owned demo server for operator exclusivity. Issue one grant against
  the fresh state hash and full implementation commit.
- [x] Run a new exclusive, single-invocation qualifier with the existing trusted
  certificate bundle. Do not replay earlier attempt drivers. Save the result,
  validated sections, usage and failure details privately.
- [x] Check all six earlier attempts, four prior grants, 70 prior usage records,
  requirements/playback revision 3, ledger, transcript, brief and compiler count.
  Verify attempt 8 is rejected before provider or save. On success, audit the
  graph, both views, source coverage, constraints, artifacts and runner checks,
  then present the exact plan for review. On failure, stop and record it.
- [x] Restore the local demo preview, update README with the measured outcome,
  check paths and `git diff --check`, and commit documentation separately.

Offline verification: the first new regression failed because `preflight` did
not accept `seventh_attempt`. The implementation passed 32 seventh-attempt tests
and 20 existing section-repair cases, Ruff, whitespace checks and all 16 scripted
demo cases with no provider calls. A fresh full run passed **571 tests**, with the
existing Windows symlink skip and Starlette/httpx deprecation warning, in 435.38
seconds. Persistent logs and JUnit output remain ignored under the attempt-7
evidence directory so a paused terminal cannot lose the result.

Read-only preflight reproduced the exact earlier missing-exclusions response
inside the merged shared repair wrapper. The original raw session hash is
unchanged: six attempts, four consumed grants, 70 responses, approved requirements
revision 3, one compiled brief and estimated cumulative spend of $0.14736118.
The configured Codex profile qualified without inference; no plan is approved for
execution. Diff, security and cleanup review retained the existing source checks,
budget, repair limits, CAS reservation, private grant fields and human review gates.

## Observed result: provider overload; live qualification incomplete

Implementation checkpoint `86bbe93` was committed before issuance. A fresh
compare-and-swap preflight issued one seventh-attempt grant with the exact approval
quote and full implementation hash. The qualifier was invoked once with verified
TLS, the original model/settings and no automatic HTTP retries.

The outline passed schema and deterministic validation. The screen request then
returned **HTTP 529**, with provider error type `server_error` and message
`worker overloaded`. It produced no accepted screen or phase. The repaired phase
validation boundary was therefore not reached; this run does not qualify that
repair against a live phase response. The session is blocked with no complete
plan or plan approval, and no Codex worker was dispatched.

One successful response recorded 2,576 input and 2,350 output tokens, estimated
new spend **$0.0028878**, bringing cumulative recorded spend to **$0.15024898**
and usage to 71 responses. The failed HTTP response is retained separately from
successful-response usage. Two logical passes were reserved. The grant is consumed;
attempt 8 is rejected before constructing a provider or saving state.

Postflight verified all six previous attempts, four previous grants, 70 earlier
usage records, ledger, transcript, approved requirements/playback revision 3,
compiled brief and compiler count are unchanged. Raw provider response bodies,
validated outline, redacted report, backup and postflight evidence remain ignored
under `.data/live-check/2026-10-29/attempt-7/`. Do not replay `run.py`.

The currently running demo was backed up and restored against its existing
`C:/Users/jiang/Intent/.data/prompt-caller.sqlite3`, preserving all three sessions.
Both `/` and `/workspace` returned HTTP 200 and API health remained `demo`.
Both primary local checkouts are synced to merged `main` at `13b06f8`; the retest
implementation and this outcome remain on `codex/live-planning-retest`. Further
provider inference requires a separately bounded authorization; no eighth grant
was issued. Plan, context and phase approval gates remain intact.
