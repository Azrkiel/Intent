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
- [ ] Save private baseline evidence under `.data/live-check/2026-10-29/attempt-5/`.
  Verify stopped server, existing credentials/trust, approved revision 3, four
  failed attempts and 65 usage records. Record exact approval and implementation
  hash through the operator CLI. Never reset or clone the session.
- [ ] Run the production qualifier once with the existing TLS trust bundle.
  Maximum nine logical passes and two responses per pass; 4096 output tokens per
  response and the existing $2 session budget remain unchanged. Save validated
  responses/failure details privately. Assert four old attempts, both old grants,
  prior usage, requirements, playback approval and compiled brief are preserved.
- [ ] Validate successful plan coverage, both rendered views, graph and runner
  compatibility, then stop for separate human plan approval. On failure, report
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
estimated spend against the unchanged $2 budget. No live call has been made yet.
