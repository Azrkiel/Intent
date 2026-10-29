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

- [x] Add regression tests in `backend/tests/test_framework.py` before production
  changes. Run `uv run pytest backend/tests/test_framework.py -q`; expect failure
  because vague six-slot sessions are currently ready and framework contracts are absent.
- [x] Implement framework entries/areas/questions, map/reviewer contracts, structural
  citation/coverage validation, source hashing, deterministic gate checks and bounded
  demo context. Add Session storage; run the regression tests and ledger tests.
- [x] Add map/reviewer prompts and engine passes with application-owned identities,
  fail-closed invalidation, mandatory clarification candidates and context propagation
  to compiler, playback and phase planner. Test provider failures, insufficient review,
  stale state, persistence and API approval/build refusal. Preserve scripted demo tests.
- [x] Add `frontend/components/framework-review.tsx` and typed framework state.
  Surface current review, blockers and proposed/confirmed map entries beside Clarity.
  Add render/visibility regressions and an end-to-end demo workspace test.
- [x] Run `uv run pytest -q`, `uv run ruff check backend`, `npm test`,
  `npm run typecheck`, `npm run build`, `npm run eval:demo`, and the focused browser
  check. Expect all checks to pass; record any existing failures separately.
- [x] Review correctness, security and unnecessary complexity, commit coherent verified
  milestones, integrate locally, restart the owned localhost servers and verify health
  and workspace rendering. Do not push or claim live model qualification without keys.

## Verification results

- Full backend run: 567 passed, 1 skipped. The initial baseline exposed an existing
  Windows test-layout issue: its worker temp directory must be outside the home
  directory that contains the source checkout. The full passing run used a unique
  `--basetemp C:\Users\Public\Intent-clarity-tests-<timestamp>` directory.
- Follow-up checks cover reanalysis approval invalidation and the full 160-entry
  framework allowance without consuming the brief's requirement-line limit. The
  integrated main checkout passed all 30 framework regressions and Ruff.
- Frontend: 48 unit tests, TypeScript checking and production build passed.
- All 4 browser regressions passed; framework screenshots were inspected at desktop
  and mobile sizes. All 16 scripted demo evaluation flows completed.
- Review checked failed/partial passes, source freshness, citation validation,
  approval invalidation, prompt/data boundaries and downstream proposal labeling.
  No new execution permissions or credential paths were introduced.
- Integrated locally into `C:\Users\jiang\Intent` and restarted loopback servers.
  API health is OK and `/workspace` returns HTTP 200 with the existing session DB.
- Live model quality remains unqualified: localhost is still demo mode with no
  configured model credentials. No paid model calls were made.

Code checkpoints: `d76e2a8` (gate/contracts), `66b1eaa` (workspace UI),
`9c2c982` (mapping/review pipeline, lifecycle and downstream context).
