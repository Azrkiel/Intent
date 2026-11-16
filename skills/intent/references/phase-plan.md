# Phase plan and agent handoff

Only after an approved brief, and only if the user wants a plan.

## Shape

Use the smallest coherent decomposition. The limits are ceilings, not targets; a small
self-contained app can be one phase with one package.

- **Outline:** a cited specification (one statement per confirmed ledger ID, marked
  confirmed), journeys, architecture, visible proposed choices, and common rules holding
  every constraint and exclusion. At most **4 ordered phases**, each depending only on
  earlier ones, and at most **3 screens**, each with its states (empty, loading, error,
  success where relevant). No screens for a project without screens.
- **Phase:** at most **2 work packages**.
- **Work package:** at most **3 ordered tasks**, with owned paths, interfaces,
  preconditions, inputs and outputs, steps, acceptance, checks (an exact command and its
  expected result), artifacts, exclusions and open choices.

## Rules

- Cite ledger IDs on every statement. Technology and UX assumptions are proposals;
  unresolved choices stay visible and are never quietly settled in a task step.
- Every confirmed requirement maps to some package's acceptance, marked confirmed with its
  ID. Every constraint and non-goal is repeated in each package's exclusions.
- Every deferred decision is resolved before the phase it's due in.
- Distinguish absent or uninitialized data from corrupt data and from failed reads or
  writes. Implement stated failure behaviour without inventing extra mechanisms.
- No placeholder inputs or preconditions ("None", "N/A", "TBD").
- Shared interfaces have one producer; dependents consume them.
- One plan, several views: a human view (vision, journeys, wireframes, proposals) and an
  engineering view (architecture, dependency graph, tasks) render from the same plan, so
  they can't disagree.

## Review between phases

Each phase ends with a human review before the next starts: show what was built, which
acceptance checks passed (with their actual output), and what changed from the plan. Plan
approval, permission to run commands and phase acceptance are separate yeses.

## Handing work packages to agents

For each package, give the worker only: the common rules, the root and its phase context,
its own package and tasks, the exact ledger quotes it relies on, and its declared inputs.
Dependencies don't grant access to sibling packages' instructions. In Claude Code this is
a subagent prompt; in Codex, a task with the package text and the relevant `AGENTS.md`.
