# Framework-backed clarity implementation

Goal: require a complete, independently reviewed framework before live build readiness.

Architecture: add bounded framework contracts and deterministic validation in
`backend/app/framework.py`; persist a revision/hash-bound review on Session.
The engine maps and reviews intent before ranking and readiness. A separate workspace
component displays the map and blockers. Existing phase planning remains post-approval.

Stack: Python/Pydantic/FastAPI, React/Next.js/TypeScript, pytest/Vitest/Playwright.

```
utterance -> invalidate review -> extract -> six critics
                                           |
                                           v
                                  draft framework -> independent review
                                    |                    |
                         invalid/failed -> blocked       |
                                    |          user decision needed -> question
                                    |                    |
                                    +--- retry <--- next utterance
                                                         |
                                         complete/current -> playback approval
                                                         |
                                               brief + phase planning
```

- [ ] Add regression tests in `backend/tests/test_framework.py` before production
  changes. Run `uv run pytest backend/tests/test_framework.py -q`; expect failure
  because vague six-slot sessions are currently ready and framework contracts are absent.
- [ ] Implement framework entries/areas/questions, map/reviewer contracts, structural
  citation/coverage validation, source hashing, deterministic gate checks and bounded
  demo context. Add Session storage; run the regression tests and ledger tests.
- [ ] Add map/reviewer prompts and engine passes with application-owned identities,
  fail-closed invalidation, mandatory clarification candidates and context propagation
  to compiler, playback and phase planner. Test provider failures, insufficient review,
  stale state, persistence and API approval/build refusal. Preserve scripted demo tests.
- [ ] Add `frontend/components/framework-review.tsx` and typed framework state.
  Surface current review, blockers and proposed/confirmed map entries beside Clarity.
  Add render/visibility regressions and an end-to-end demo workspace test.
- [ ] Run `uv run pytest -q`, `uv run ruff check backend`, `npm test`,
  `npm run typecheck`, `npm run build`, `npm run eval:demo`, and the focused browser
  check. Expect all checks to pass; record any existing failures separately.
- [ ] Review correctness, security and unnecessary complexity, commit coherent verified
  milestones, integrate locally, restart the owned localhost servers and verify health
  and workspace rendering. Do not push or claim live model qualification without keys.
