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
- `backend/app/planning/validation.py`: scope deterministic errors and build review entries;
  keep existing statement traversal/citation consumers and historical serialization.
- `backend/app/planning/service.py`: translate plan-relative errors to current proposal paths,
  scope runner failures and require the expanded review catalog.
- `backend/app/planning/prompts.py`: concrete inputs/readiness and full prose-review guidance.
- `backend/tests/test_planning_field_repair.py`: captured-shape sanitized regression and
  strict replacement, whole-validation, unknown-path, budget and cancellation cases.
- `backend/tests/test_planning_prose_review.py`: review inventory and rejection/omission gates.
- Existing mock-provider tests: emit scoped replacements when requested, rather than the old
  whole-document response. Their original acceptance/failure assertions remain authoritative.

## Steps

- [ ] Write a phase regression with empty inputs/preconditions and three valid tasks.
  Mock the second response as `{"R1": ["Approved requirements"], "R2": ["Accepted outline"]}`.
  Run `uv run pytest backend/tests/test_planning_field_repair.py -q -x`: expect failure
  because the current adapter interprets the replacement object as a complete phase.
- [ ] Implement `ScopedError(message, paths)` and `FieldRepair(schema, original, error)`.
  Resolve each path against actual JSON and Pydantic annotations; use rebuilt field annotations
  to create required `R1...Rn` fields with `extra="forbid"`. Reject duplicate JSON keys,
  ambiguous locations and overlapping scopes. `apply(content)` copies the original and
  replaces only bound fields before calling the original checked schema.
- [ ] Update `LiveModels.call` to use `FieldRepair` for parseable outline/screen/phase errors.
  Its second request retains original context but supplies the replacement schema and scope
  descriptions. No third response. Malformed JSON and output limits keep one complete retry.
  Run the field suite: expected pass, at most two recorded responses per call.
- [ ] Test and add explicit error scopes for citations, outline coverage/dependencies,
  screen states, package exclusions/acceptance, unsafe paths, dependencies/interfaces and
  runner checks. Translate only current-phase paths; historical-section errors stay blocked.
  Adapt synthetic transports through one test helper that reads application-owned scopes.
  Run model, outline, section, request-contract, response-boundary and acceptance suites.
- [ ] Write review-inventory and negative-flow regressions before adding `review_catalog(plan)`.
  Preserve existing `S` entries and add deterministic `F` entries with exact paths/text and
  explicitly absent citations/status for uncited text. Include all specified prose; reject
  capacity above 500 before verifier invocation. Update service payload and prompts.
  Run `uv run pytest backend/tests/test_planning_prose_review.py -q`: expected pass.
- [ ] Exercise retained captured phase failures offline with the real original field values
  and a mocked provider, never saving to the retained store. Check unchanged historical
  hashes and no approval/dispatch; record private diagnostics under ignored `.data/`.
- [ ] Run focused regressions, full `uv run pytest -q` with a unique non-overlapping
  `--basetemp` under `C:/Users/Public`, Ruff, all demo evaluations and whitespace checks.
  Persist long-running logs under `.data/`. Review correctness/security/cleanup and commit
  each verified milestone. Record exact outcomes, limitations and checkpoint hashes.

No newer-checkout merge, live request, grant, source correction or plan approval is authorized.
