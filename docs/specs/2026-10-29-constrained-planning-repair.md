# Constrained planning repair and complete prose review

Status: approved by the user: "approve, please continue"; implemented and verified offline at `fa00240`.
Scope: offline continuation of the [eighth-attempt handoff](../../.Codex/handoffs/2026-10-29-1610.md).
This design grants no additional live attempt, plan approval, export or dispatch.

## Evidence and problem

The original eighth phase contained exactly two schema failures:
`packages[0].preconditions` and `packages[0].inputs` were empty. Its one
whole-object repair replaced those lists with `"None"` and changed a previously
valid three-task list into six tasks, duplicating the original block. Both
responses were valid JSON with finish reason `stop`. This is schema failure,
not JSON parsing failure, truncation or a transport failure.

On resumption, an in-memory diagnostic reproduced both sets of validation errors.
Replacing only the two empty lists with explicitly labeled diagnostic values
allowed the original phase to pass the current whole-plan deterministic checks.
The diagnostic did not save or semantically approve a plan. All five captured
input files retained their SHA-256 hashes; no provider was constructed or called.
The private report is `.data/offline-repair-design/2026-10-29/diagnosis.json`.

The reconstructed diagnostic plan has 30 catalogued `Statement` records.
Architecture, phase flow, package flow, task read/write steps and empty-screen
text are present in the complete verifier payload but absent from its explicit
review checklist. Completeness of that checklist therefore does not establish
review of those fields. Their prose includes the already documented missing-data,
failed-read and unresolved-update-order risks.

## Alternatives

1. **Recommended: application-scoped field replacements and a broader review
   catalog.** The application binds repair values to known invalid paths and
   checks the entire reconstruction. This prevents unrelated task duplication
   while retaining semantic rejection. It requires explicit error scopes.
2. **Continue whole-object repair with stronger prompts.** Lowest change cost,
   but attempt 8 directly demonstrates that this can break valid fields. Prompt
   changes alone cannot enforce preservation.
3. **Regenerate individual packages or add repair calls.** Smaller output than
   an entire phase, but still allows valid sibling content to change and expands
   inference or orchestration boundaries. Defer; keep the existing response cap.

## Repair protocol

Apply constrained repair to planner outline, screen and phase proposal roles.
Other model roles retain their existing contracts. `planner:verify` retains its
separate coverage-repair behavior: genuine semantic rejection must stop without
asking the reviewer to clear its rejection or missing-requirement lists.

For a complete, parseable proposal that fails validation:

- Extract bounded, application-owned error scopes. Pydantic field locations must
  resolve to real schema fields and actual object/list positions. A missing field
  is repairable only when its existing parent and schema field are unambiguous.
- Assign opaque replacement keys such as `R1` and `R2`. The request describes the
  exact target, its original value, expected field schema, validation reason and
  relevant source context. Source text remains data. The model supplies values
  for these keys, never paths, operations, approvals or a replacement document.
- Generate a strict replacement schema for exactly these keys. Retain original
  field constraints, including nested list limits, exact refs and forbidden extra
  fields. Reject missing, extra, duplicate or incorrectly typed replacement keys.
- Resolve every scope against the original JSON before applying anything.
  Coalesce repeated scopes and reject ambiguous/overlapping scopes. Never widen
  an error to the document root or an arbitrary valid ancestor to permit repair.
- Copy the original object and replace the allowed fields atomically. Preserve
  all other parsed JSON values exactly, including task order and multiplicity.
  Check this invariant before validation; do not mutate the captured original.
- Run the original checked schema over the entire reconstruction, including
  citations, coverage, accepted references, ownership/dependencies and enabled
  runner policy. Retain independent service checks and final semantic review.
- Stop after an invalid repair. There is no third response, silent truncation,
  task deduplication, inserted citation, invented default or follow-up repair.

Existing deterministic acceptance errors currently surface at the model root.
Give supported failures explicit application-owned scopes: for example missing
specification coverage targets `specification`, missing constraints target
`common_rules`, and a runner-command failure targets that check's command.
Paths must identify the actual offending fields; cross-field failures require
explicit, tested scopes. Unmapped root errors, forbidden extra keys and ambiguous
locations stop safely. They do not authorize whole-object rewriting. Document
this narrower repair eligibility and adjust boundary tests deliberately.

When the original response is malformed JSON or ends with `length`, there is no
trustworthy complete object to preserve. Retain the existing single complete
regeneration for those cases, with the same full validation and response cap.
Do not salvage fragments. A malformed or truncated replacement also stops.

The same model, 4096-token planner output cap, nine logical passes, two responses
per pass, usage accounting and cumulative budget remain in force. Existing
attempt-scoped transport policy is unchanged; this work issues no grants.
Report parsing, output-limit, field-schema and deterministic-acceptance failures
accurately without exposing raw provider content or request credentials.

## Inputs and readiness

Keep the current nonempty inputs/preconditions contract for this increment.
A package already has real planning inputs: approved source requirements, the
accepted outline and the requested phase. Dependencies contribute outputs only
when they actually exist. Prompts should request these concrete inputs and
distinguish readiness required before execution from state already satisfied.
Do not claim that the generated plan is approved while it is being drafted.

Do not prescribe counter behavior through these fields or auto-fill them in the
adapter. The provider must propose their values and review must assess them.
`"None"` or another placeholder cannot establish a real input or readiness fact.
Genuinely optional lists may be a useful later contract change, but do not lower
minimum lengths to rescue this captured response. That change needs separate
examples and acceptance criteria; it is outside this repair increment.

## Explicit semantic review coverage

Keep persisted proposal/plan schemas and their serialization unchanged. Retain
the existing `Statement` traversal and citation validation for current consumers.
Add an ephemeral review catalog rather than synthesizing confirmed statements or
citations for plain strings. Existing statement entries keep their `S` keys;
additional text entries have deterministic application-owned keys and source paths.

Review entries carry kind, path, text, and actual citations/status when present.
Uncited text is explicitly uncited and assessed against the complete ledger and
surrounding plan. Its presence in a confirmed package must not turn it into a
confirmed source fact. Preserve existing string bounds, including the larger
architecture/diagram allowance; never truncate text to fit a review entry.

Include architecture; screen wireframes and titles; phase titles and flows;
package flows, preconditions, inputs, outputs, ownership and artifacts; task
titles and every step; check expectations; and all existing cited statements.
Treat IDs, reference tokens, enum values, dependency refs and command argv as
structural data validated by existing checks and retained in the full plan context.
Source snapshots are evidence, not generated claims requiring fabricated review
records. Audit this inventory against every proposal field in a coverage test.

The verifier must return the exact complete catalog key set. Keep the existing
500-entry limit and output/pass budgets. Reject an oversized catalog before the
verifier request; do not omit fields, batch extra calls or silently raise limits.
Missing coverage may use the same one existing review repair only when the
reviewer has reported no semantic rejection or missing confirmed requirement.
Any genuine rejection blocks readiness and remains authoritative even if review
coverage is incomplete.

Review instructions explicitly distinguish absent data, invalid stored values
and failed I/O; reject unsupported restrictions and executable steps that settle
an open choice while listing it as unresolved elsewhere. Also assess coherent
ownership and output production, including any proposed source-to-dist operation.
These instructions are general; the retained counter ledger is an offline test
case, not a hardcoded product rule.

## Offline acceptance criteria

- Reproduce the two original empty-list errors and the raw six-task repair.
  Exercise field replacements against the original captured phase in an isolated
  fixture. Exact non-target subtree equality must include its original three tasks.
- Reject extra/duplicate keys, model-chosen paths, missing replacements, invalid
  nested values, overlapping/ambiguous scopes and mutation of valid siblings.
  Rerun independent constraints after reconstruction, including a separate task
  count fault and cross-field reference, citation, exclusion and runner failures.
- Cover malformed/truncated originals and repairs, root checks, unknown locations,
  exhausted repair allowance, cancellation and budget failure. Prove at most two
  responses per pass, unchanged usage recording and no provider fallback.
- Test actual input/readiness text and a placeholder negative case. Do not weaken
  validation to produce a green fixture.
- Assert every listed prose field has an explicit review entry and the original
  text/path. Omission or rejection of any new entry must block readiness.
- Use captured absence/read-error/open-choice prose as named negative fixtures.
  A scripted reviewer must reject these entries through the production failure
  gate, with no approval, export or worker dispatch. This proves routing and gate
  enforcement, not that a live model will reliably recognize the contradiction.
- Keep captured evidence private. Commit a minimal sanitized regression fixture
  so tests do not require ignored files, the retained session or any credential.
- Run relevant focused tests, `uv run pytest -q`, `uv run ruff check backend`,
  `uv run python -m backend.evals.run --demo` and `git diff --check` for the
  implementation. No frontend source change is proposed.

## Integration boundary and checkpoints

The clean continuation branch starts at `f325d97` in the phase-four worktree.
The separate `C:/Users/jiang/Intent` checkout was first inspected at `18edcde`
and advanced to `7fad434` during this investigation, with a modified
`frontend/next-env.d.ts`. Its five feature/documentation commits add framework review, alter live
readiness, pass reviewed framework context into planning, and change model token
and finish-reason handling. It is a separate checkout; this worktree's local
`main` still points at `13b06f8`. Inspect actual commits, not the stale ref.
The sixth commit adds only its framework-clarity handoff; the overlapping source
diff remains the one inspected at `18edcde`.

Implement and verify offline here first, using small local commits. Before any
later integration, preserve both histories and inspect the actual overlapping
domain/model/service changes. Do not overwrite the newer readiness requirements
or the generated frontend modification. An old retained session lacking current
framework evidence may correctly be blocked under the newer readiness gate;
never fabricate that evidence to replay it. Requalification of the combined
checkout is separate from this branch's checks.

The user approved this concrete design and offline implementation. The
[implementation record](../plans/2026-10-29-constrained-planning-repair.md) captures
test-first changes, captured-response rehearsals and verification outcomes.
No ninth invocation, limit reset, live session clone, source alteration or human
plan approval is implied.

## Design-checkpoint validation

The draft's relative links and referenced implementation paths exist, and the
staged whitespace check passed before the design commit. The existing baseline
command `uv run pytest backend/tests/test_models.py backend/tests/test_planning_acceptance_repair.py -q`
passed all 18 tests in 4.44 seconds. This checks existing adapter and acceptance
behavior, not the proposed implementation. No full suite was rerun for this
documentation-only checkpoint. The captured after-state still validates as eight
attempts, effective allowance eight, a consumed eighth grant, and no active or
approved plan. No retained driver was executed.
