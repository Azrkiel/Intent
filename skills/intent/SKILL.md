---
name: intent
description: Turns a rough software idea into a cited build brief a coding agent can follow without guessing. Keeps an Intent Ledger of what the user actually said (exact quotes), asks one build-changing question at a time with 2-3 concrete options, drafts specific answers for the user to confirm, and only writes the brief (CLAUDE.md or AGENTS.md) and phase plan once a gate passes. Use when someone describes an app, tool or feature they want built but the request is vague or underspecified ("I want an app that...", "build me something to...", "spec this out", "turn my idea into a brief/PRD/plan", "what do you need to know before building this?"), or when they ask for the Intent method. Not for clear, fully specified coding tasks.
---

# Intent: build what they mean

Coding agents build what was typed, not what was meant. A one-line idea like "a habit
tracker that syncs automatically" hides a dozen decisions the builder would silently guess.
This skill finds the decisions that would change the build, asks only about those, and
hands over a brief where nothing is invented.

**One principle:** ask only what would change the build, and never pass off a guess as
the user's word.

## Hard rules

1. **Confirmed needs a quote.** A ledger item is `confirmed` only with an exact verbatim
   substring of the user's own message. Never quote your own question. No quote means
   `inferred`. A draft the user picks counts as their words, marked `(drafted)`.
2. **One question per turn**, the single most build-changing one, with 2-3 concrete
   options and one line on what each would change in the code. Never ask what a sensible,
   reversible default can settle.
3. **Propose, then confirm.** When an answer is missing or vague, write the most plausible
   specific answer yourself, list what you assumed, and let the user pick, edit or reject
   it. Never adopt a draft they didn't pick.
4. **One-way doors are always the user's.** Data model, identity/accounts, external
   integrations, and deleting or overwriting user data are never defaulted. Two-way doors
   may be defaulted and listed under "Choices I made for you" with a veto.
5. **Stay proportional.** A personal tool gets no accounts, servers, sync, payments or
   scale unless the user's words need them. Respect explicit exclusions; never reopen them.
6. **New words reopen the gate.** Any new user statement after approval invalidates the
   playback approval and the brief until they are re-confirmed.
7. **Be honest about checks.** Report a check as passed only if you ran it. If readers or
   candidate builds were not independent (no subagents), say the check was done inline.

## Choose a mode first

- **Quick** (throwaway script, small personal tool, user says "keep it light"): ledger +
  critics + playback + brief. Skip the North Star rubric, reader agreement and the map.
- **Full** (shared tool or product, money/data/identity involved, or the user asks): every
  step below.

Say which mode you picked in one line; the user can switch.

## The loop

1. **Listen and record.** Extract each independently actionable clause from the user's
   message into the ledger with its quote. Save it to `INTENT.md` in the project root (use
   `templates/INTENT.md`) when a filesystem is available, otherwise keep it in the chat.
   See `references/ledger.md`.
2. **North Star (full mode).** Make six fields specific, in this order: Who & when, Job,
   Ambition, Today, Good looks like, Fails if. Check each against its rubric and the
   vague-word lexicon (`scripts/lexicon.py`), read it back in one sentence, and if you can,
   have two independent readers answer probes about it (`scripts/agreement.py`). See
   `references/north-star.md`.
3. **Find the gaps.** Run the six critic lenses (data, identity & access, behaviour words,
   contradictions, edges & failure, done-ness). Score each candidate question and drop any
   whose options would build the same code. In full mode, discover decisions by divergence:
   ask several independent candidate builders the same probes and turn disagreements into
   decisions. See `references/critics-and-decisions.md`.
4. **Ask or decide.** Ask the top one-way or must-have decision. Default the rest with a
   stated reason. Record each as a decision. Go back to step 1 with the answer.
5. **Map the product (full mode).** Fill the eight areas (purpose, journeys, structure,
   data, access, failure-recovery, verification, scope) with cited entries marked
   `confirmed`, `proposal` or `unresolved`, write Given/When/Then scenarios, then review
   the map independently. See `references/framework-map.md`.
6. **Gate.** Walk the checklist in `references/gate-playback-brief.md`. If anything is
   open, name it and return to step 3.
7. **Playback.** At most three plain sentences, then ask "What did I get wrong?". Show
   "Choices I made for you". Wait for explicit approval.
8. **Brief.** Compile the cited brief (`templates/brief.md`): every line cites ledger IDs,
   inferred items go under Undecided. Verify it both ways: no line adds anything the
   ledger doesn't support, and every confirmed item appears. Write it to `CLAUDE.md` for
   Claude Code or `AGENTS.md` for Codex (ask which if unclear; default to the one already
   in the repo).
9. **Phase plan (if asked).** Break the brief into small phases and work packages with
   acceptance checks and a human review between phases. See `references/phase-plan.md`.

## Asking a question

Use this shape, one per turn:

> You said "syncs automatically". Which is closest?
> 1. Saved in this browser only (no server; nothing to set up)
> 2. Synced through your own cloud drive file (no accounts; one integration)
> 3. Synced through an account on a small server (accounts, a database, hosting)
> Or tell me in your own words.

When drafting instead: *My best guess from what you told me: "…". I filled in: … Does that
fit, or would you pick one of these?* followed by 2-3 alternatives.

## What to show the user

Keep the ledger and checks visible but short: a progress line such as
`Gate: 4/6 slots confirmed · 1 one-way decision open · North Star 5/6`, the current
question, and on request the full `INTENT.md`. Never bury the question under the ledger.

## References

- `references/ledger.md`: item types, statuses, slots, extraction rules, file format.
- `references/north-star.md`: the six fields, rubric rules, G1-G4 checks, drafting.
- `references/critics-and-decisions.md`: lenses, scoring, divergence, disposition, records.
- `references/framework-map.md`: eight areas, claims, scenarios, independent review.
- `references/gate-playback-brief.md`: gate checklist, playback, brief and verification.
- `references/phase-plan.md`: phases, work packages, review, agent handoff.
