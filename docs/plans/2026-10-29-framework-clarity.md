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

## Live qualification follow-up, 2026-10-29

The user authorized live qualification with a total $0.50 allowance. Credentials
were available in the existing phase-four Intent worktree's ignored `.env`; they
were read in memory without being printed or copied into the main checkout.
Tests used fresh live sessions in separate ignored databases and the current main
implementation. Builds and Codex execution remained disabled. The existing main
session database was not used for these interviews.

**Outcome: live qualification did not pass.** The readiness gate stayed closed
on vague input and provider failures, but neither a complete concrete interview
nor semantic fidelity of an accepted framework was established.

- Initial protocol smoke: Nano returned no grounded requirements; Lightning
  extracted four. A later Nano repeat extracted four after one schema repair.
  This establishes intermittent extraction, not a passing smoke qualification.
- A vague idea stayed blocked and approval returned HTTP 409. Its map nonetheless
  invented substantial task-management, cloud-sync and automation scope. The
  independent reviewer returned no issues; unresolved questions kept the gate shut.
- The first concrete interview timed out during extraction. The shorter repeat
  consumed both 4,096-token output allowances with `finish_reason=length` and
  no answer content. Neither attempt produced a complete concrete framework.
- A separate explicit reasoning-control comparison requested Nano thinking off.
  It answered quickly but attempted to update nonexistent IDs such as `goal`;
  the application rejected the result. This comparison did not qualify that
  configuration or change the main checkout's settings.
- Correction attempts remained blocked and stale approval requests returned 409.
  No genuine prior approval or compiled brief existed, so these attempts do not
  establish successful live approval/brief invalidation or settled exclusions.
- A component-only check supplied a manually prepared synthetic ledger with exact
  source quotes, then called the real Super mapper and reviewer. This deliberately
  bypassed extraction and critics and is not end-to-end quality evidence. All eight
  areas, 21 entries, citations and review addresses passed structural validation.
  The reviewer returned no issues, and framework blockers were empty.
- Manual inspection rejected that component result: technical defaults such as
  the storage key and no-framework implementation were labeled confirmed; swipe
  deletion and a disabled Add button were invented as confirmed behavior; the
  duplicate-URL allowance was omitted despite its cited ledger item being counted
  as covered. Reset wording did not unambiguously preserve waiting for the user's
  click before clearing data. An empty model review is therefore insufficient
  evidence of semantic fidelity, even when structural checks pass.

The default Python HTTP client's certificate trust initially failed before any
model call. The isolated test clients used `ssl.create_default_context()` to load
Windows trust, retaining TLS certificate verification. Authentication and model
listing then succeeded. No production trust configuration was changed.

Paid calls stopped after 32 dispatched requests. The cumulative conservative
ledger was **$0.311454**, including full reservations for two uncertain failed
requests, leaving **$0.188546** of the authorized allowance unallocated. The
aggregate limiter reserved every request and repair before dispatch, across all
sessions and comparisons. It valued returned tokens at $1/$3 per million
input/output, above the application's Nano/Super estimates, with an input framing
allowance. This is a conservative local estimate, not a provider invoice or
verified current account tariff. No additional allowance was assumed on resume.

Ignored evidence under `.data/live-check/`:

- `qualification-20261029-172521`: initial smoke and interviews.
- `qualification-20261029-182500`: shared-budget extraction repeat and shorter case.
- `qualification-20261029-182754`: explicit reasoning-control comparison.
- `qualification-20261029-182856`: component fixture, map, review, cumulative budget
  and `human-review.json`; its summary explicitly records failed human acceptance.

Next engineering work should reproduce extraction output exhaustion and invalid
update IDs, then address unsupported confirmed map claims, clause-level omissions
and reviewer misses without weakening the fail-closed gate. A fresh full interview
must still demonstrate an acceptable concrete map, actual playback approval,
compilation and correction invalidation before claiming live qualification. No
production fix or new full regression run is claimed by this follow-up.
