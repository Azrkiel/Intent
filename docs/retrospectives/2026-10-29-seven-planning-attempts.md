# What seven live planning attempts taught us

## Scope and evidence

This review was written before the eighth request. It covers all seven retained
attempt records, the available failure diagnostics, rejected candidates, usage
reports, implementation records, and the current production adapter and service.
The source is the existing counter-app session, approved requirements revision 3.
No previous attempt, response, approval or source was rewritten for this review.

All seven attempts failed to produce a complete plan. Their boundaries were
different; treating every failure as bad JSON or provider instability would hide
the work needed. Raw artifacts remain private under `.data/live-check/`. The
first handoff was session handoff 2026-10-29-1533 (not retained).

## Attempt-by-attempt findings

| Attempt | Observed failure | Why it happened | Prevention for attempt 8 |
| --- | --- | --- | --- |
| 1 | `Specification misses confirmed requirements`; two responses, no accepted outline | Schema-valid output did not cover every confirmed requirement as confirmed specification. Citation presence elsewhere did not satisfy specification coverage. The semantic acceptance check ran after the adapter's repair opportunity. | Retain application-owned confirmed/unconfirmed ID checklists and the checked outline schema. Reproduce omitted coverage offline; the same one repair must see the real coverage error. |
| 2 | `Diagrams must use plain ASCII`; all seven confirmed IDs covered, one schema-valid response with finish reason `stop` | The presentation constraint was outside the provider schema. Useful content was rejected for Unicode diagrams after schema acceptance. This was not a truncation failure. | Retain bounded Unicode descriptions, length/control checks and post-call validation. Prefer concise prose to diagrams. Do not reintroduce the obsolete ASCII restriction. |
| 3 | Accepted outline and screen; phase returned `ui-setup-phase` instead of `ui-setup` after its repair | The general phase schema allowed a reference that contradicted the accepted outline. Application validation caught it after repair. The rejected phase also proposed shell checks and a placeholder command unsupported by the runner. | Keep exact-reference request schemas. Move runner compatibility into the same checked phase boundary when execution is enabled, while retaining dispatch preflight. |
| 4 | Outline exhausted two responses; final diagnostic was `string_pattern_mismatch` at `architecture` | ASCII remained a value constraint and the repair prompt emphasized JSON structure. The first response used 4096 output tokens, but its raw text and finish reason were not saved; truncation cannot be asserted. | Retain value-aware repair and bounded Unicode. Reject actual `finish_reason=length`, request a compact complete repair, and capture finish reasons and bodies privately. |
| 5 | Schema-valid outline omitted L4 from `common_rules`; no outline accepted | Coverage in specification did not propagate constraints into common rules. This deterministic check still ran outside repair. Manual review also found incorrect first-launch handling and unsupported numeric/tab-key rules. | Retain the constraint-ID checklist and shared semantic repair. Explicitly distinguish absent data, corrupt data and failed I/O; keep unspecified mechanisms and decisions proposed or unresolved. |
| 6 | Accepted outline and screen; both first-phase packages omitted L4 from exclusions | The repaired phase was schema-valid but lacked required scope exclusions. The initial schema error had already consumed repair. Its exact original detail was not retained. Outline-only repair fixes had left section checks outside the same boundary. | Retain checked screen/phase schemas, every-package exclusion checklists and final coverage checks. Capture every new response and validation detail. Do not patch missing citations into historical model output. |
| 7 | Accepted outline; screen request returned HTTP 529 with `worker overloaded` | This was a provider server error, not a JSON or requirement-validation failure. SDK retries were correctly disabled, but there was no explicit bounded application-level recovery for transient HTTP overload. | Allow at most two recorded overload retries across attempt 8, with bounded backoff, budget reservation and no second retry layer. Do not restart the plan or replenish attempt allowance. |

Evidence locations, relative to `.data/live-check/`:

- Attempts 1–2: `2026-10-28/planning-attempt-1/` and `planning-attempt-2/`.
- Attempt 3: `2026-10-28/extension-attempt-3/`, especially `failure-audit.json`
  and the rejected phase candidate.
- Attempt 4: `2026-10-28/requalification-attempt-4/`, including
  `planner-outline-failure.json`.
- Attempts 5–6: `2026-10-29/attempt-5/` and `attempt-6/`, including their
  `failure-diagnostic.json` and rejected proposal artifacts.
- Attempt 7: `2026-10-29/attempt-7/`, including the successful outline, raw
  provider response 02, `outcome.json` and `postflight.json`.

The dedicated implementation/outcome records are the
[third](../plans/2026-10-28-planning-requalification-proposal.md),
[fourth](../plans/2026-10-28-fourth-attempt-requalification-proposal.md),
[fifth](../plans/2026-10-29-fifth-planning-attempt.md),
[sixth](../plans/2026-10-29-sixth-planning-attempt.md), and
[seventh](../plans/2026-10-29-live-planning-retest.md) records.

## What worked, and why

The application rejected incomplete or incompatible plans instead of treating
well-formed JSON as sufficient. Exact source quotes, canonical references,
constraint coverage and separate approval gates preserved the approved intent.
That protection must remain even when it makes an attempted run fail.

Explicit ID checklists improved coverage: attempt 2 covered all seven confirmed
IDs; later accepted outlines also retained the scope exclusion. Exact-reference
schemas and the runner-policy payload addressed concrete errors observed in
attempt 3. Attempt 6's proposed commands matched the supported Git inspection
command, showing progress on that boundary even though its exclusions failed.

Bounded Unicode removed an unnecessary presentation obstacle. A model can provide
a short explanation without drawing an elaborate diagram. Output-limit detection
now checks the actual finish reason rather than guessing from token counts.

The shared checked-schema wrapper is the useful architectural correction. It
gives the existing single repair the same deterministic evidence that the service
will use to accept a section. Tests exercise schema failure followed by semantic
failure without allowing a third model response.

History preservation worked throughout. The retained session still has its
approved requirements and brief, seven failed attempts, five consumed exceptional
grants, and 71 successful-response usage records. Recorded spend is estimated at
$0.15024898 against the existing $2 budget. Atomic issuance and reservation,
exclusive drivers and stop-on-failure behavior prevented silent replay.

Attempt 7 improved observability: raw response bodies and validated content were
saved privately without request headers or credentials. Persistent test logs also
survived a paused terminal. The final prior full run passed 571 backend tests;
that supports software invariants, not live model quality.

## What did not work, and why

The team repeatedly fixed the latest failed boundary without walking every later
acceptance boundary. Coverage, references and exclusions were each caught too late
for repair in different runs. Two remaining instances are visible in current code:
runner compatibility is checked at dispatch but not section acceptance, and final
reviewed-statement completeness is checked after the verifier returns. Attempt 8
will move only those deterministic checks into repair; an actual semantic
rejection must still fail the plan.

The fifth candidate demonstrates why citation coverage alone is insufficient.
It treated an absent storage key as a failed read, introduced a non-negative
integer rule, and invented tab-specific keys. The seventh outline still described
an optimistic update sequence while listing the update strategy as an open
choice. These are fidelity risks, not missing formatting. Stronger instructions
and final semantic review are required; inventing a decision to get a green result
would defeat the application.

Some candidates split a small single-page counter into three phases and several
packages. That adds calls, handoffs, repeated claims and opportunities for drift.
The plan should use the smallest coherent decomposition that meets the ledger;
it does not need to use the schema's maximum counts.

Provider overload should not be addressed by changing JSON repair or resetting
an entire plan. The transport policy needs its own small, visible budget.
Conversely, authentication errors, semantic failures and ambiguous timeouts should
not be hidden behind automatic retries.

Earlier diagnostics did not retain every failed response. We cannot identify
attempt 4's exact offending characters or attempt 6's initial schema error.
Those limits remain explicit rather than being filled with a plausible story.

## The proposed eighth attempt

1. Preserve the current model, TLS verification, approved sources, nine logical
   passes, one content repair per pass, 4096 output tokens and cumulative $2 budget.
2. Add one audited eighth grant. Bind it to all seven prior attempt hashes and
   the consumed seventh grant. No ninth attempt or replay is permitted.
3. Add at most two explicit retries for HTTP 502/503/504/529 across the entire
   eighth attempt. Use 3s then 10s backoff, honor a longer `Retry-After` up to 30s,
   and stop rather than violate a longer requested wait. Keep SDK retries at zero.
   This permits at most 20 HTTP posts and 18 successful model responses. Record
   every retry and conservatively reserve its possible cost; do not invent usage
   for a failed HTTP response whose billing is unknown.
4. Put runner checks and final review-coverage completeness inside checked schemas.
   Preserve the independent post-call guards. Never repair a genuine semantic
   rejection into approval merely by clearing its rejection list.
5. Ask for the smallest useful plan, concise prose and explicit separation of
   confirmed behavior from open decisions. Distinguish absent, invalid and failed
   storage operations without adding counter-specific requirements to the ledger.
6. Rehearse the complete pipeline offline with the actual retained ledger and
   strict source guards. Inject omitted exclusions, bad references/commands,
   incomplete verifier coverage, mixed content errors, overload recovery and
   exhausted transport budget. This is a protocol rehearsal, not quality evidence.
7. After tests and review pass, invoke a new exclusive production driver once.
   Audit a successful plan's source fidelity, graph/views, Markdown snapshot,
   export gate and runner compatibility before presenting the exact plan for
   human review. If it fails, retain the real failure and stop automatic inference.

The provider's [cookbook](https://dev.nebius.com/cookbook/first-agent-on-nebius)
supports capped application-owned backoff with SDK retries disabled. Our policy
is narrower and attempt-scoped. The [public status page](https://status.nebius.com/)
reported operational service when checked, but that does not prove a particular
model worker will accept the next request. The saved HTTP 529 remains the evidence
for attempt 7.

These changes improve the odds and make any failure diagnosable. They do not
guarantee provider availability or faithful model output, and success will not be
claimed from a fixture or from a partial plan.

## What attempt 8 added to the evidence

The authorized eighth run was prepared with 640 passing backend tests, one skip,
95 passing focused checks, seven offline full-pipeline rehearsals and all 16 demo
evaluations. It nevertheless failed. Those checks established bounded protocol
behavior and history preservation; they could not establish faithful live output.
The detailed [eighth-attempt record](../plans/2026-10-29-eighth-planning-attempt.md)
contains the measured result and proposed follow-up.

What worked: the model used one phase/package, the outline and screen passed
without repair, references and L4 exclusions were present in the rejected phase,
and every task used the supported runner command. The original schema errors
were supplied to the one repair. HTTP responses and finish reasons make the
failure reproducible. No overload occurred, so bounded overload recovery remains
offline-tested rather than live-demonstrated. All prior source/history and gates
survived; the demo returned with the same sessions.

What failed: initial empty `preconditions` and `inputs` violated minimum lengths.
The full-object repair fixed those fields but emitted two identical three-task
blocks, violating the independent three-task maximum. Both bodies were valid JSON
and ended with `stop`. Captured-response replay confirmed this is in the provider
output, not a concatenation in the adapter. Improving the repair prompt did not
prevent a new error in previously valid fields. "Valid JSON" is also a misleading
public diagnostic when JSON parsing succeeded but schema validation failed.

Why the preparation was insufficient: rehearsals injected known failures into
otherwise faithful fixtures. They demonstrated enforcement, not the model's
ability to obey all structural constraints and preserve requirement semantics at
once. General instructions also did not eliminate earlier fidelity drift: the
rejected phase still conflates absent data and read failures, and commits update
ordering while that choice remains open. A shape-only fix would be insufficient.

The next credible direction is constrained field repair with whole-document
validation, plus semantic review of free-form architecture, flow and task steps.
Test it offline on these real captured failures before requesting any further
live attempt. Do not relax the task limit, deduplicate model output into approval,
or accept placeholder inputs merely to get green checks. Attempt 8 consumed
$0.01464840 estimated; no ninth attempt was made or authorized.
