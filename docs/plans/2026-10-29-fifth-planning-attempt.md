# Fifth live planning attempt

Goal: run exactly one human-authorized fifth attempt on the retained approved session.
Architecture: append a separate fifth-attempt grant bound to the consumed fourth
grant, four immutable attempt hashes, session and approved requirements revision.
Keep the default two attempts, existing grants, budget, models and repair bounds.
Stack: existing Python, Pydantic, SQLite and pytest; no frontend change.

Authorization: "try a fifth please, let's make this work". This authorizes the
necessary grant implementation and one attempt, not plan approval, agent dispatch,
another attempt, publishing, merging or release.

```text
Stopped server + fresh preflight + exact human approval
  -> eligible four-failure snapshot -> CAS save fifth_attempt grant
       changed/duplicate/ineligible -> reject without provider
  -> CAS reserve revision 5 + consume grant before provider
       valid -> immutable plan + human/engineering views -> review required
       failure/cancel/restart -> retain evidence, no automatic replay
  -> attempt 6 rejected before provider/save
Correction before reservation -> invalidate unused grant, retain history
```

Files: `contracts.py` defines `PlanningFifthAttempt` and validates its chain;
`allowance.py` supplies the shared limit; `service.py` consumes the grant;
`domain.py`, `engine.py`, `store.py` enforce session binding, invalidation and
preservation; `planning_extension.py` exposes local `--fifth-attempt` preflight
and issuance, with audit fields excluded from public output. New tests live in
`backend/tests/test_planning_fifth_attempt.py`.

- [x] Write and run failing regressions for fifth issuance/generation, sixth
  refusal, immutable prior history, CAS, invalidation/restart and public redaction.
- [x] Add the grant and CLI selector, preserving all existing grant behavior.
  Run focused tests, then `uv run pytest -q` and `uv run ruff check backend`.
  Expected: all tests pass, existing Windows symlink skip may remain. Inspect
  the diff and `git diff --check`; commit the verified implementation.
- [x] Save private baseline evidence under `.data/live-check/2026-10-29/attempt-5/`.
  Verify stopped server, existing credentials/trust, approved revision 3, four
  failed attempts and 65 usage records. Record exact approval and implementation
  hash through the operator CLI. Never reset or clone the session.
- [x] Run the production qualifier once with the existing TLS trust bundle.
  Maximum nine logical passes and two responses per pass; 4096 output tokens per
  response and the existing $2 session budget remain unchanged. Save validated
  responses/failure details privately. Assert four old attempts, both old grants,
  prior usage, requirements, playback approval and compiled brief are preserved.
- [x] Complete the applicable outcome branch: for a successful plan, validate
  coverage, both rendered views, graph and runner compatibility, then stop for
  separate human plan approval. On failure, report
  the exact failed boundary and retained diagnostics. Verify attempt 6 is refused
  without provider/save. Update observed documentation and commit separately.

Baseline: 70 extension/requalification tests passed before implementation.
The fourth failure was the obsolete ASCII architecture constraint; merged bounded
Unicode and output-limit handling address that boundary without weakening coverage.

Verification: 33 new regressions passed. The full backend suite passed 448 tests,
with one existing Windows symlink skip and the Starlette/httpx deprecation warning,
in 411.69 seconds. Ruff and whitespace checks passed. All 16 scripted demo
evaluations passed with zero provider calls. Diff/security inspection covered
atomic grant issuance/reservation, immutable prior evidence, closed failure/restart
gates, local-only issuance and public audit redaction; no blocker was found. Cleanup
reuses the existing operator CLI, settings, store and model adapter.
The read-only live preflight confirmed
revision 3, four consumed attempts, 65 usage records and $0.13261738 cumulative
estimated spend against the unchanged $2 budget. That preflight made no live call.

## Observed fifth-attempt result

Implementation checkpoint: `8f51a9a`. The separate grant recorded the exact approval
above and full implementation hash. One production qualifier invocation made one
Super request. Its outline passed schema and Unicode validation, but deterministic
acceptance failed with `Common rules miss constraints or exclusions`. L4 ("No login,
network, backend, or sync") was missing from `common_rules`; all seven confirmed IDs
were covered in specification. No outline section was accepted or active plan saved.

Usage: 2,531 input tokens, 2,416 output tokens, 12,734 ms latency, estimated
$0.00293370 new cost. Cumulative usage is 66 responses and $0.13555108. All three
grants are consumed. Read-only postflight confirmed unchanged requirements,
playback approval, brief, compiler count, four old attempts, both old grants and
65 prior usage records. Attempt 6 is rejected before provider construction/save.

Manual fidelity inspection found the architecture wrongly treats a missing saved
value as a storage failure and disables first-use interaction. Common rules also
assert a non-negative-integer restriction and per-tab storage keys without explicit
source support. Adding the missing citation would not establish a faithful plan.

## Offline repair follow-up

The model adapter's two-response loop previously validated only the base response
schema; `accept_outline` ran afterward. A schema-valid missing rule therefore
terminated the attempt after one response. The correction wraps `OutlineProposal`
with the existing deterministic validator for the current source ledger and adds
`constraint_ledger_ids` to application-owned context and the outline prompt. Keep
the post-call validator as a guard against non-adapter providers. No validation is
removed, no source text is synthesized and no third response is possible.

```text
Outline response -> schema + source/coverage/dependency checks
  valid -> accept outline
  invalid -> one shared repair -> valid: accept / invalid: preserve failure
```

Eleven new mocked-HTTP regressions cover missing common rules/specification/choices,
unknown citations, bad dependencies, repaired success, repeated rejection, retained
usage and a schema failure followed by a semantic failure without a third response.
The checklist test now checks confirmed constraint/non-goal IDs too. Before the
correction, ten tests failed at the expected boundary; after it, all 139 focused
planning/response/grant tests passed. Repair checkpoint `219b1eb` then passed a fresh
full suite: 459 passed, one existing Windows symlink skip and one deprecation warning
in 533.03 seconds. Ruff, whitespace checks and all 16 scripted demo evaluations
passed; the demos made zero provider calls. Review/security inspection confirmed
that source/citation/dependency validation and the response/budget limits are
retained. Cleanup uses Pydantic validators and the existing adapter without a new
retry loop or dependency. Read-only postflight confirms the raw live state is
unchanged through the offline correction.

This correction has no new live evidence and does not repair or replay attempt 5.
No complete plan, rendered plan views or approved export was produced; those audits
remain pending. Further live qualification needs separate human authorization.
The two code checkpoints are local on `codex/fifth-live-planning`; no new push, PR,
merge or release was requested or made. The retained checkout is clean after the
documentation checkpoint that records this result.
