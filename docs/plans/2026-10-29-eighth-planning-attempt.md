# Eighth attempt based on seven-attempt review

Goal: produce a complete, source-faithful live plan from the retained approved
counter-app requirements, applying the documented lessons from attempts 1–7.

Architecture: preserve prior history and add one CAS-bound eighth grant. Use the
existing checked-schema repair for every deterministic acceptance boundary and an
attempt-scoped, append-only transport retry ledger for at most two overload
retries. Keep the ordinary two-attempt policy and all human approval gates.
Stack: Python, Pydantic, SQLite, existing OpenAI-compatible adapter, HTTPX and pytest.

The user explicitly authorized an eighth attempt and required the handoff and
all-attempt review first. The [handoff](../../.Codex/handoffs/2026-10-29-1533.md)
was committed at `fbf9c0b` before reviewing historical attempts. The completed
[retrospective](../retrospectives/2026-10-29-seven-planning-attempts.md) supplies the
evidence and rationale. Execute this plan within that authorization; no additional
permission is needed to start. It grants no ninth attempt or unseen plan approval.

```text
handoff -> seven-attempt evidence review -> this plan -> failing regressions
  -> eighth grant + checked acceptance + bounded transport recovery -> tests
  -> implementation commit -> fresh source/history snapshot + backup + CAS issue
  -> CAS reserve attempt 8 / consume grant
       HTTP 502/503/504/529 -> <=2 recorded retries total -> bounded backoff
       invalid content -> existing one repair -> accept section or stop
       valid complete candidate -> full semantic review -> immutable review-ready plan
  -> fidelity + graph/views + notes/export/runner audit -> human plan review
failure/cancel/restart -> preserve accepted prefix and all evidence; no ninth attempt
```

## File responsibilities

- `backend/app/planning/contracts.py`: `PlanningEighthAttempt`, seven prior hashes,
  consumed seventh-grant binding and at most two `PlanningTransportRetry` records.
  A retry record holds role, HTTP status, delay, time and conservative cost reserve.
- `backend/app/planning/allowance.py`: shared effective allowance of eight only for
  the new valid grant; defaults remain two.
- `backend/app/{domain,engine,store}.py`: session binding, public redaction,
  correction invalidation, immutable prior history, append-only retry audit.
- `backend/planning_extension.py`: local `--eighth-attempt` selector with fresh
  state-hash CAS, exact approval, reason and implementation commit.
- `backend/app/models.py`: one retry owner; SDK retry count stays zero. Retry only
  explicit 502/503/504/529 responses for the consumed eighth grant's reserved
  planning pass. At most two retries total, 3s/10s backoff, at most 30s per wait.
  Stop on authentication/content errors, exhausted retry quota/budget, long
  Retry-After or ambiguous connection/timeout failures. Include retry cost risk in
  subsequent budget checks without adding fabricated successful-response usage.
- `backend/app/planning/service.py`: consume the eighth grant atomically; apply
  `preflight_checks` before accepting each package when execution is enabled; use
  a checked verifier schema for exact reviewed-statement coverage. Keep semantic
  rejection and missing-requirement checks authoritative after the call.
- `backend/app/planning/prompts.py`: compact decomposition and prose; distinguish
  absence, invalid input and failed operations; keep unresolved choices unresolved.
- Tests: `test_planning_eighth_attempt.py`, `test_planning_transport_retry.py`,
  and `test_planning_acceptance_repair.py` cover these public boundaries with real
  model-adapter calls against mocked HTTP.
- `.data/live-check/2026-10-29/attempt-8/`: private snapshots, exclusive marker,
  every HTTP response body/finish reason, retry audit, logs and measured outcome.

## Steps and acceptance criteria

- [x] Write eighth-grant tests first. Run
  `uv run pytest backend/tests/test_planning_eighth_attempt.py -q -x`; expect
  failure because `eighth_attempt` is not supported. Cover CAS issuance/reservation,
  default exhaustion, nine refusal, history, redaction, correction, restart,
  rollback and immutable audit fields. Add only the existing grant pattern plus
  an append-only, two-record transport list on the new grant; do not change the
  serialization of historical `PlanAttempt` records or their hashes.
- [x] Write retry tests before changing the adapter. Run
  `uv run pytest backend/tests/test_planning_transport_retry.py -q -x`; expect a
  one-off HTTP 529 to fail without recovery. Implement the bounded policy described
  above, then verify transient recovery, shared quota across roles, content repair
  independence, no retries for 400/401/403/429/connection/timeouts, cancellation,
  retry timing, budget risk reservation and persistence. No global retry setting.
- [x] Write acceptance-boundary regressions. Run
  `uv run pytest backend/tests/test_planning_acceptance_repair.py -q -x`; expect
  bad runner commands or incomplete review coverage to terminate before repair.
  Wrap only these deterministic checks; preserve genuine semantic rejection.
  Keep execution-disabled exports' proposed-command behavior unchanged. Adapt
  the scripted fixture to the explicitly supplied runner policy when enabled.
- [x] Update prompts with the retrospective's concise, general fidelity guidance.
  No counter-specific decision, source quote or requirement is synthesized.
- [x] Rehearse the complete plan pipeline using the real retained ledger with a
  mocked transport and injected failures. Assert exact source preservation, no
  approval, all runner checks compatible and a single shared repair per pass.
  Test results are offline protocol evidence only.
- [x] Run focused tests, `uv run pytest -q`, `uv run ruff check backend`,
  `uv run python -m backend.evals.run --demo`, and `git diff --check`. Persist full
  logs/JUnit under `.data/`. Review retry accounting, immutable history, API
  redaction, source/fidelity gates and cleanup; commit the verified checkpoint.
- [ ] Recheck the live session: revision 3 approved, seven failures, five consumed
  grants, 71 prior usage records, original ledger/transcript/brief/compiler count,
  estimated spend $0.15024898, same key/model/TLS and cumulative $2 budget. Back it
  up, stop the owned demo, record the exact current authorization and CAS-issue
  one eighth grant against the fresh hash and implementation commit.
- [ ] Invoke the new exclusive driver once. Allow at most nine logical passes,
  18 successful model responses, two extra overload HTTP posts and 30s per delay.
  Keep 4096 output tokens, one content repair and no hidden SDK retries. Capture
  bodies, finish reasons and retry metadata privately; redact console output.
- [ ] Check the applicable result. Success requires a complete persisted plan,
  exact semantic review coverage with no rejected/missing claims, manual fidelity
  audit against the ledger, valid runner commands, consistent graph/views and
  notes snapshot, and a closed export/worker gate pending human plan approval.
  Failure requires its exact boundary and retained evidence, not an invented pass.
  Verify all seven prior attempts, grants and usage are unchanged, transport audit
  is append-only and attempt 9 is rejected before provider/save.
- [ ] Restore the same demo database and sessions. Record the measured outcome,
  update README and the handoff, check paths/whitespace, and commit documentation
  separately. Report the plan or remaining blocker and checkpoint hashes.

## Verified implementation checkpoint

TDD reproduced the absent eighth grant, unrecovered HTTP 529 and late runner
acceptance failures before implementation. The 95 focused checks pass. Seven
full-pipeline rehearsals used a temporary copy of the retained ledger and mocked
HTTP, with zero provider calls and no live-state changes. All 16 demo evaluations
pass. The complete backend suite passed with 640 tests, one Windows symlink skip
and one existing Starlette deprecation warning in 554.87 seconds. Ruff and
`git diff --check` pass. No frontend source changed.

Manual review checked immutable historical hashes, operator-only CAS issuance,
private grant redaction, append-only retry records, shared retry and budget limits,
SDK retry disabling, and genuine semantic rejection. Cleanup retained the existing
grant pattern and acceptance wrapper. The live eighth attempt remains unstarted
at this checkpoint; rehearsals do not establish live model quality.
