---
name: intent
description: Takes a rough software idea and builds the whole project hands-off. First it interviews the user until it understands what they want and how they make product decisions (goals, principles, trade-offs, taste), then it builds autonomously, steering by that understanding, adding features it judges serve the user's goals, and reporting what it built, added and decided at the end. Use when someone wants an app, tool or product built from an idea and wants the agent to run with it ("I want an app that...", "build this for me end to end", "take this idea and run with it", "make the whole thing, don't ask me every step"), or asks for the Intent method. Not for small, fully specified coding tasks.
---

# Intent: understand once, then steer

Coding agents build what was typed, not what was meant, and they stop to ask about every
gap. Intent works the other way: it spends the human's time once, up front, learning what
they are after and how they decide, then builds the entire project without asking again. It
behaves like a product owner who knows the user's goals, not a spec-taker: when a feature
would clearly serve those goals, it builds it and says so afterwards.

**One principle:** understand the user well enough to decide as they would, and never pass
off your own decision as their words.

## Two stages

1. **Understand** (the only stage that talks to the user). Learn the goal, the North Star,
   the user's principles and trade-offs, and their taste; settle every one-way decision;
   collect what only a human can provide; end with one approval of the charter. See
   `references/understand.md`.
2. **Steer** (no questions). Plan, build, verify with real checks, decide what nobody
   anticipated by the charter's rules, add aligned features within a budget, and finish with
   a report. See `references/steer.md`.

When the user approves the charter, tell them plainly: *"I won't ask you anything else
until the report, unless I hit a stop condition."* Then keep that promise.

## Hard rules

1. **Provenance on everything.** Every requirement, decision and feature is labeled by
   origin: `user` (exact quote from their message), `drafted` (a draft the user picked), or
   `intent` (your own call, with the goal it serves). Never present an `intent` item as the
   user's.
2. **Learn the why and the how-you-decide, not only the what.** A list of features can't
   steer; principles, trade-offs and worked yes/no examples can.
3. **Propose, then confirm.** In Understand, when an answer is missing or vague, draft the
   most plausible specific answer, list your assumptions, and let the user pick or edit. One
   question per turn, with 2-3 concrete options.
4. **One-way doors belong to the user.** Accounts and identity, the data model's storage
   and anything that needs a migration to undo, external or paid services, deleting or
   overwriting user data, credentials, spending money, and publishing anything outward.
   Settle them in Understand. In Steer, never cross one for a feature you added on your own;
   if the build itself forces an unforeseen one, take a reversible path or stop (rule 7).
5. **Additions must pass the alignment test** in `references/steer.md`: serve a named
   North Star outcome or principle, fit the Ambition, break no non-goal, cross no one-way
   door, stay reversible and isolated, fit the budget, and win the proxy vote.
6. **Must-haves first, done means checked.** Additions start only after every must-have
   passes its check. "Done" means the charter's acceptance commands pass, with their output.
7. **Stop conditions are the only reason to come back early.** They are listed in the
   charter. Anything else, decide, log it, and keep going.
8. **Be honest about checks.** Report a check as run only if you ran it. If proxies,
   readers or builders weren't independent subagents, say so and halve the addition budget.

## Depth scales with Ambition

| Ambition (from the North Star) | Understand covers | Addition budget default |
| --- | --- | --- |
| Throwaway script | Job, Good looks like, Fails if; 3 calibration items | none |
| Personal tool | full North Star, 3 principles, 5 calibration items | small |
| Shared with a few people | full North Star, principles, trade-offs, 6-8 calibration items | small |
| Product | everything in `references/understand.md` | moderate |

Say which depth you picked in one line; the user can change it.

## State on disk

Keep everything in the project so a fresh session or another agent can resume:

- `INTENT.md` (`templates/INTENT.md`): ledger, North Star, principles, calibration,
  decisions, and during Steer the run state and decision log.
- `CHARTER.md` (`templates/charter.md`): the approved charter the build follows.
  Reference it from the agent's instructions file instead of pasting it there: add
  `@CHARTER.md` to `CLAUDE.md` for Claude Code, or "Read CHARTER.md before any work" to
  `AGENTS.md` for Codex.
- `INTENT-REPORT.md` (`templates/report.md`): the end-of-run report.

If the user edits a file or speaks during Steer, treat it as a new turn: update the ledger
and charter, log the change, and continue without re-running Understand unless it touches
a one-way door.

## References

- `references/understand.md`: the interview, in order, and its gate.
- `references/ledger.md`: ledger items, provenance, extraction rules.
- `references/north-star.md`: the six fields, rubric, checks G1-G4, drafting.
- `references/critics-and-decisions.md`: finding build-changing gaps; builder divergence.
- `references/charter.md`: playback, the charter's sections, and verifying it.
- `references/steer.md`: the autonomous loop, decision policy, alignment test, proxy vote,
  budget, stop conditions, report.
- `references/phase-plan.md`: phases, work packages and automated phase gates.
- `scripts/lexicon.py`: vague-word scan (G1).
- `scripts/agreement.py`: two-reader agreement (G4, optional).
- `scripts/proxy_check.py`: how well proxies predict the user's calibration answers.
