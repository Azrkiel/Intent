# Critics and decisions

## The six critic lenses

Run each lens over the ledger (and the North Star in full mode). Each lens finds gaps only
within its own scope and proposes at most 3 questions. In Claude Code or Codex you can run
the lenses as parallel subagents; otherwise run them one after another.

| Lens | Looks for |
| --- | --- |
| Data & persistence | what is stored, where, how long, how it syncs |
| Identity & access | who uses it, accounts, ownership, visibility |
| Behaviour words | ambiguous "automatic", "smart", "fast", "simple" behaviours |
| Contradictions | requirements whose implementations need reconciling, e.g. cross-device persistence with no identity mechanism |
| Edges & failure | empty states, errors, offline, realistic scale |
| Done-ness | observable success criteria; the first thing the user will check |

Each candidate question has:

- 2-3 concrete, plausible, distinct options;
- a **code diff**: at most 3 plain sentences naming the files, tables, services, APIs or
  libraries that differ between options (never code);
- the ledger IDs it targets, and the slot it fills if any;
- scores **divergence**, **uncertainty**, **cost to change**, each 1-3.

Critic rules: never restate a confirmed item as a question, never repeat an answered one,
never reopen an explicit exclusion, no cosmetic questions when a default will do, and
return nothing when the lens has no build-changing uncertainty left.

## Scoring (impact)

`impact = divergence × uncertainty × cost_to_change` (1-27)

- **Divergence:** 3 incompatible architectures or data models; 2 meaningful behaviour
  change; 1 cosmetic or a small local guard with an ordinary default. **Divergence 1 means
  drop the question.**
- **Cost to change later:** 1 a local function, handler, validation or label; 2 changes
  across module interfaces; 3 a database migration, authentication boundary or external
  integration.
- **Uncertainty:** how unsettled the ledger leaves it.

Don't score hypothetical extreme scale as uncertainty unless the user stated a need. Rank
by impact, prefer contradictions on ties, and skip anything already asked. Questions with
impact >= 12 block the gate until answered or decided.

These numbers order questions; they are not measurements. Say "this changes the data
model" rather than "impact 18".

## Divergence-first decisions (full mode)

Rather than trusting one model's sense of what's ambiguous, look for real disagreement:

1. Write decision **probes**: points where two reasonable builders could build different
   code from the current claims. Seed them from the critic questions. Each probe has 2-3
   options with the code difference, context citing ledger/claim IDs, the North Star fields
   it serves (drivers), a Kano class (must-be, performance, delighter), a category
   (data-model, identity, external, destructive, behavior, presentation, other), and,
   only if it can safely wait, a due phase like `P2`.
2. Ask **4 independent candidate builders** (subagents given only the North Star, claims
   and probes) which option each would actually build, or -1 if nothing tells them.
3. If all four agree, drop the probe: there is nothing to ask. Otherwise it is a decision.

Without subagents, simulate builders inline only as a last resort and say so; prefer the
critic scores in that case.

## Choosing the next decision

`score = split × importance × reversibility_weight − repeat_penalty`

- **split:** how evenly the builders divide (normalized entropy; an even split is most
  informative).
- **importance:** must-be 3, performance 2, delighter 1.
- **reversibility_weight:** one-way 3, two-way 1.
- **repeat_penalty:** 0.5 × earlier questions on the same aspect.

Ask the top decision, one per turn.

## Disposition (first matching row wins)

| Decision | What happens |
| --- | --- |
| One-way door (data-model, identity, external, destructive) | Always asked. Never defaulted. |
| Two-way, ≥ 70% of builders agree (3 of 4) | Default to the majority; list under "Choices I made for you" with a one-click veto. |
| Must-be, two-way, less agreement | Asked. |
| Delighter | Default it, or exclude it as a nice-to-have nobody needs yet. |
| Can wait until a later phase | Deferred with a due phase; the plan must resolve it before that phase starts. |

**Stop rule:** stop asking when the best remaining two-way decision scores below 1.5; take
the majority option as a default. One-way decisions never stop.

## Decision record

```text
D3  status: open | decided | delegated | deferred(due=P2) | excluded
    context: one sentence, cites L/C IDs
    drivers: North Star fields it serves (e.g. good, fails-if)
    options: 2-3, each with code difference
    outcome: chosen option, "because" + a driver
    owner: user (with quote) | delegated (majority, veto offered)
    consequences: claims it adds or removes
    confirmation: the scenario that shows the build follows it
    reversibility: one-way | two-way      kano: must-be | performance | delighter
```

## Decision Quality

Score each decision on six links; quality is the weakest link.

| Link | Present when |
| --- | --- |
| Frame | context cites claims; drivers name a North Star field |
| Alternatives | ≥ 2 options with distinct code differences |
| Information | options grounded in builder divergence or cited ledger text |
| Values | the outcome's "because" names a driver |
| Reasoning | consequences list the claims added or removed |
| Commitment | user quote or delegation record, plus a confirmation scenario |

One-way decisions need every link. Two-way decisions need every link except a user quote.

A question whose answer changed no decision, claim or scenario was wasted. If you notice
several, raise your bar for asking.
