# Offline constrained planning repair

Goal: preserve valid proposal content during one repair and require explicit semantic review of plan prose.
Architecture: application-owned error paths bind typed replacement values to invalid fields;
the original checked schema validates the whole reconstruction. A separate ephemeral
review catalog covers cited statements and uncited prose without changing saved plans.
Stack: Python, Pydantic, HTTPX mock transport, pytest, existing SQLite store.

Approved design: [specification](../specs/2026-10-29-constrained-planning-repair.md).
User approved implementation in this session. Execute locally; no live inference or integration is included.

```text
proposal -> validate -> valid -> semantic review -> human review
              |
              +-- field errors -> typed replacements -> reconstruct -> validate
              +-- malformed/length -> complete retry -> validate
              +-- ambiguous error / failed repair / rejection -> blocked
```

## Files

- `backend/app/planning/repair.py`: strict JSON, typed field resolution, scoped errors,
  replacement schema and atomic reconstruction, with no dependency on sessions/providers.
- `backend/app/models.py`: select scoped repair only for complete planning proposals;
  preserve accounting, transport retries and the two-response cap; accurate diagnostics.
- `backend/app/planning/validation.py`: scope deterministic errors; keep existing
  statement traversal/citation consumers and historical serialization.
- `backend/app/planning/review.py`: ephemeral cited/prose review entries and capacity bound.
- `backend/app/planning/service.py`: translate plan-relative errors to current proposal paths,
  scope runner failures and require the expanded review catalog.
- `backend/app/planning/prompts.py`: concrete inputs/readiness and full prose-review guidance.
- `backend/tests/test_planning_field_repair.py`: captured-shape sanitized regression and
  strict replacement, whole-validation, unknown-path, budget and cancellation cases.
- `backend/tests/test_planning_prose_review.py`: review inventory and rejection/omission gates.
- Existing mock-provider tests: emit scoped replacements when requested, rather than the old
  whole-document response. Their original acceptance/failure assertions remain authoritative.

## Steps

- [x] Write a phase regression with empty inputs/preconditions and three valid tasks.
  Mock the second response as `{"R1": ["Approved requirements"], "R2": ["Accepted outline"]}`.
  Run `uv run pytest backend/tests/test_planning_field_repair.py -q -x`: expect failure
  because the current adapter interprets the replacement object as a complete phase.
- [x] Implement `ScopedError(message, *paths)` and `FieldRepair(schema, original, error)`.
  Resolve each path against actual JSON and Pydantic annotations; use rebuilt field annotations
  to create required `R1...Rn` fields with `extra="forbid"`. Reject duplicate JSON keys,
  ambiguous locations and overlapping scopes. `apply(content)` copies the original and
  replaces only bound fields before calling the original checked schema.
- [x] Update `LiveModels.call` to use `FieldRepair` for parseable outline/screen/phase errors.
  Its second request retains original context but supplies the replacement schema and scope
  descriptions. No third response. Malformed JSON and output limits keep one complete retry.
  Run the field suite: expected pass, at most two recorded responses per call.
- [x] Test and add explicit error scopes for citations, outline coverage/dependencies,
  screen states, package exclusions/acceptance, unsafe paths, dependencies/interfaces and
  runner checks. Translate only current-phase paths; historical-section errors stay blocked.
  Adapt synthetic transports through one test helper that reads application-owned scopes.
  Run model, outline, section, request-contract, response-boundary and acceptance suites.
- [x] Write review-inventory and negative-flow regressions before adding `review_catalog(plan)`.
  Preserve existing `S` entries and add deterministic `F` entries with exact paths/text and
  explicitly absent citations/status for uncited text. Include all specified prose; reject
  capacity above 500 before verifier invocation. Update service payload and prompts.
  Run `uv run pytest backend/tests/test_planning_prose_review.py -q`: expected pass.
- [x] Exercise retained captured phase failures offline with the real original field values
  and a mocked provider, never saving to the retained store. Check unchanged historical
  hashes and no approval/dispatch; record private diagnostics under ignored `.data/`.
- [x] Run focused regressions, full `uv run pytest -q` with a unique non-overlapping
  `--basetemp` under `C:/Users/Public`, Ruff, all demo evaluations and whitespace checks.
  Persist long-running logs under `.data/`. Review correctness/security/cleanup and commit
  each verified milestone. Record exact outcomes, limitations and checkpoint hashes.

No newer-checkout merge, live request, grant, source correction or plan approval is authorized.

## Captured-response rehearsal evidence

Two isolated SQLite rehearsals replayed the retained outline, screen and original
phase through the production adapter/service with mocked HTTP at `test.invalid`.
The first supplied typed replacements for only the two empty lists. The original
three tasks remained exactly intact; a scripted verifier then rejected three
explicitly indexed flow/task-step entries. Five mock responses were recorded and
readiness remained blocked. The second returned the captured six-task whole-object
repair as the replacement response: the adapter refused it after four mock responses,
without accepting a phase or requesting a third phase response.

Both rehearsals preserved the seven original attempt hashes, approved sources,
transcript, brief/compiler state and prior usage prefix. Neither opened the retained
store, approved a plan or dispatched a worker. Captured input file hashes were
unchanged. `.data/offline-repair-design/2026-10-29/rehearsal.json` contains the private
report; all added usage was simulated in temporary stores. These tests establish
preservation and rejection routing, not live model semantic judgment.

## Review findings addressed

- A dependency traversal initially scoped an unknown dependency to its valid
  consumer. A failing regression demonstrated the wrong path; traversal now reports
  the package that actually contains the unknown edge or cycle.
- Top-level JSON values of the wrong type were initially labeled deterministic
  acceptance failures. A failing regression reproduced this; only root `value_error`
  checks get that category, while wrong-shape JSON remains a schema failure.
- Existing synthetic providers now return only requested replacement keys. The
  original source/usage, accepted-prefix, one-repair and failure assertions remain.
- Manual correctness/security review checked typed path resolution, forbidden and
  duplicate keys, atomic reconstruction, unchanged historical formats, command
  restrictions and approval boundaries. The new code interprets no model-selected
  paths as filesystem operations and introduces no execution or network authority.
- Cleanup keeps replacement logic and ephemeral review data in separate small
  modules. Existing statement/citation consumers remain intact; no persistent
  proposal, session, grant or history model was changed.

The first full-suite process ended without an exit result; its partial log is
retained as `backend-interrupted.log` and is not counted as passing evidence.
Subsequent runs use hidden persistent launchers and separate exit-status files.

The first completed run reported 673 passed, two failed, one Windows skip and the
existing Starlette warning in 580.20 seconds. One older sixth-attempt synthetic
provider still returned a whole object for repair; it now uses the same scoped
response helper, with its history/usage/attempt assertions unchanged. The 68-case
sixth-attempt plus new field/prose suites passed after that fixture correction.

The other failure exposed an existing Windows path-length limit: the long
`C:/Users/Public/Intent-repair-tests-<32-character-id>` temp prefix plus the
long-path regression's nested workspace caused `FileNotFoundError`, `WinError 3`,
while creating staging Git metadata. The same unchanged test passed in 13.79
seconds under `C:/Users/Public/ir-<8-character-id>` and reproduced the failure
under the long prefix. An isolated fake-worker diagnostic recorded the creation
error in `long-path-diagnosis.json`. This work does not claim to fix that unrelated
path-length limit or change the long-path assertion. The fresh complete rerun uses
the short, non-overlapping Public temp root and `backend-short.*` evidence files.

## Verified offline outcome

Implementation checkpoint: `fa00240` (`fix: constrain planning repairs and review all plan prose`).
The final full run passed **675 tests, one existing Windows skip and one existing
Starlette warning**, in 436.17 seconds. `backend-short.exit` is `0`; its log and
JUnit report are retained privately. All 35 added field/prose regressions pass;
the post-fixture focused run passed 68 cases. Ruff and staged whitespace checks
pass. All 16 zero-provider demo evaluations passed. No frontend source changed.

For another necessary full run, use a fresh short root outside the source tree:

```powershell
$intentTestRoot = Join-Path 'C:\Users\Public' ('ir-' + [guid]::NewGuid().ToString('N').Substring(0,8))
if (Test-Path -LiteralPath $intentTestRoot) { throw 'Fresh test directory unexpectedly exists' }
uv run pytest -q --basetemp $intentTestRoot
uv run ruff check backend
```

The verified result applies to this isolated repair branch. The separate newer
checkout advanced to `0a99a6c` during this work; since `7fad434`, only its framework
qualification document changed. Its generated `frontend/next-env.d.ts` modification
was preserved. No merge, push or release occurred here. Future integration must
retain its framework-readiness gate and reviewed-framework planner context and
run the relevant combined checks.

No live model call, new grant, ninth attempt, complete live plan, plan approval,
export or real worker dispatch resulted from this work. The retained eighth
failure remains the historical outcome. A future live qualification needs separate
explicit authorization and cannot reuse its consumed grant. Reliable live semantic
judgment remains unproven; field preservation and scripted rejection are the
offline evidence established here.

## Follow-up review fixes

A later review of `fa00240` found four issues, fixed in `a8cfd62` and `2d4b54d`:

- **Late review-capacity failure.** Schema-valid plans can need about 2,000 review
  entries, but the 500-entry limit was checked only after every section was paid for.
  Each outline, screen and phase now reserves the fewest entries its remaining sections
  need (a screen: purpose plus one wireframe per state; a phase: `MIN_PHASE_ENTRIES`,
  14). An oversized section fails its own validation, and the payload carries
  `review_entries_available`. The limit and the final catalog guard are unchanged.
- **No retry for unscopable output.** Extra keys, duplicate keys and unscoped root
  checks were blocked with no second response. They now get the one complete retry.
  Unresolvable application scopes and historical-section failures (now an unscoped
  `ScopedError`) still block. Field-scoped errors still use typed replacements only.
- **Cleanup.** Removed the `unchanged()` check, which could never fail, and the second
  copy of the replacement schema (it stays in the system message only).
- **MAX_PATH policy gap.** With `LongPathsEnabled` off, `exists()`/`is_symlink()` return
  False beyond 259 characters, so the worktree policy silently skipped deep metadata.
  Those calls now use extended-length paths; a regression shows a junction beyond
  MAX_PATH was previously accepted and is now rejected. Git itself still cannot open a
  worktree whose gitdir exceeds MAX_PATH, so the long-basetemp failure of the long-path
  regression remains an OS limit, not something fixed here.

Verification: 682 passed, one existing Windows skip and the existing Starlette warning,
in 499.04 seconds under a short `C:/Users/Public/ir-*` root; Ruff passes; all 16 demo
evaluations pass. The local branch was renamed `codex/constrained-planning-repair`.
Still offline only: no live call, grant, approval or dispatch.
