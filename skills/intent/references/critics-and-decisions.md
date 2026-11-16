# Critics and decisions (Understand, step 6)

The goal here is narrow: find every decision Steer would otherwise have to guess, ask the
user the one-way ones, and settle the two-way ones by the user's principles.

## The six critic lenses

Run each lens over the ledger and North Star. Each proposes at most 3 questions. In Claude
Code or Codex you can run the lenses as parallel subagents; otherwise run them in turn.

| Lens | Looks for |
| --- | --- |
| Data & persistence | what is stored, where, how long, how it syncs |
| Identity & access | who uses it, accounts, ownership, visibility |
| Behaviour words | ambiguous "automatic", "smart", "fast", "simple" behaviours |
| Contradictions | requirements whose implementations need reconciling, e.g. cross-device persistence with no identity mechanism |
| Edges & failure | empty states, errors, offline, realistic scale |
| Done-ness | observable success criteria; the first thing the user will check |

Each candidate question has 2-3 concrete options, a **code difference** (at most 3 plain
sentences naming the files, tables, services or libraries that differ, never code), the
ledger IDs it targets, and a category: data-model, identity, external, destructive (these
four are one-way), or behavior, presentation, other (two-way).

Critic rules: never restate a confirmed item as a question, never repeat an answered one,
never reopen an explicit exclusion, and drop any question whose options would build the
same code.

## Builder divergence (the "would an agent have to guess?" test)

This is the test that matters for hands-off building: if independent builders would build
different code from the same charter, Steer would be guessing.

1. Turn the critic questions into **probes**: each with its options, code difference and
   category.
2. Start **4 independent candidate builders** (subagents given only the North Star,
   principles, trade-offs, ledger and probes) and ask which option each would build, or
   -1 if nothing tells them.
3. All four agree: drop the probe; the charter already answers it.
4. They split, or any says -1: it's a decision.

Without subagents, simulate builders inline only as a last resort, say so, and treat every
probe in a one-way category as a decision.

## Disposition (first matching row wins)

| Decision | What happens |
| --- | --- |
| One-way (data-model, identity, external, destructive) | Ask the user. Never default it. |
| Two-way, a principle or trade-off settles it | Record it as `intent`, citing the principle; show it under "Choices I made for you" at playback. |
| Two-way, 3 of 4 builders agree | Default to the majority; show it under "Choices I made for you". |
| Two-way, must-have behaviour, nothing settles it | Ask, then turn the answer into a principle if it generalizes. |
| Two-way, minor | Leave it to Steer's decision policy. |

Ask the highest-stakes open decision first, one per turn: one-way before two-way, and
within each, the one whose options differ most in code.

## Decision record

```text
D3  status: open | decided | delegated | left-to-steer
    question: one sentence, cites L IDs
    options: 2-3, each with its code difference
    outcome: chosen option, "because" + a North Star field or principle
    owner: user (quote) | intent (principle P2 / builder majority 3 of 4)
    reversibility: one-way | two-way
```

A question whose answer changed no decision or check was wasted. If you notice several,
ask less and let principles decide more.
