# Phase plan

Steer plans from the approved charter. There is no human review between phases; each
phase ends at an automated gate instead.

## Shape

Use the smallest coherent decomposition. The limits are ceilings for one planning round,
not targets; a small app can be one phase with one package. For bigger scope, plan in
waves: plan up to 4 phases, build them, then re-plan the next wave from the charter and
what was learned.

- **Outline:** journeys, architecture, and common rules holding every constraint and
  non-goal from the charter. At most **4 ordered phases**, each depending only on earlier
  ones. Screens, if any, list their states (empty, loading, error, success).
- **Phase:** at most **2 work packages**.
- **Work package:** at most **3 ordered tasks**, with owned paths, interfaces, inputs and
  outputs, steps, acceptance, checks (an exact command and its expected result) and
  exclusions.

## Rules

- Every charter must-have maps to some package's acceptance, with its ID.
- Every non-goal and must-not is repeated in each package's exclusions.
- Technology and UX choices not in the charter go through the decision policy in
  `references/steer.md` and into the log; they are never quietly settled in a task step.
- Distinguish absent or uninitialized data from corrupt data and from failed reads or
  writes. Implement stated failure behaviour without inventing extra mechanisms.
- No placeholder inputs or preconditions ("None", "N/A", "TBD").
- Shared interfaces have one producer; dependents consume them.

## Phase gate

A phase is done when:

- every acceptance command in it passes, run fresh, with the output saved to the log;
- every earlier phase's checks still pass;
- `INTENT.md` run state and decision log are updated and committed.

If a gate fails, apply the retry rule in `references/steer.md`. Never move on with a
failing must-have check.

## Handing packages to subagents

When work runs in parallel, give each worker only: the charter's common rules, its own
package and tasks, the exact ledger quotes it relies on, the decision policy, and its
declared inputs. Workers log their decisions in the same format; the lead merges them into
`INTENT.md`. In Claude Code this is a subagent prompt; in Codex, a task with the package
text and `AGENTS.md`.
