# Steer: the autonomous build

Steer starts when the user approves the charter and ends with `INTENT-REPORT.md`. It never
asks the user a question. It decides by the charter, logs every decision, and stops early
only on a stop condition.

## The loop

1. **Plan.** Break the charter into phases (`references/phase-plan.md`). Must-haves come
   first; additions are never planned up front.
2. **Build a phase.** Follow the charter's commit policy: one commit per must-have, and
   later one per addition.
3. **Check.** Run the phase's acceptance commands. Fix until they pass. After 3 failed
   attempts at the same check, try one alternative approach that keeps the must-have; if
   that fails too, it's a stop condition.
4. **Decide what comes up.** Every unanticipated choice goes through the decision policy
   below and into the log.
5. **Record.** Update `INTENT.md` (run state, decision log) after every phase, so a fresh
   session can resume from the file alone.
6. **Repeat** until every must-have's check passes. Then run the addition loop. Then the
   final check and report.

## Decision policy (unanticipated choices)

Take the first rule that settles it:

1. **The charter says.** A must-have, non-goal, decision or check covers it: follow it.
2. **A principle or trade-off says.** Follow it and log which one.
3. **Calibration says.** A labeled example is close enough: follow the user's answer and
   cite it.
4. **Two-way and still open.** Take the most reversible option that fits the Ambition and
   the conventions already in the code. Log it.
5. **One-way.** If a reversible alternative still meets the must-have (local storage
   behind an interface instead of a hosted database, a mock instead of a paid API), take
   it and log why. If none exists, it's a stop condition.

Log format, one entry each:

```text
D12  phase 2 · "Sort saved articles by date added or by title?"
     chose: date added, newest first
     because: principle P2 "the newest thing is the one I want" (rule 2)
     reversible: yes · commit a1b2c3d
```

## The addition loop

Runs only after every must-have passes, and only while budget remains.

### 1. Find candidates

Look for gaps between what's built and the North Star:

- each *Good looks like* outcome: what would make it more clearly true?
- each *Fails if*: what still lets that failure happen?
- each journey: empty, error, slow and first-run states that aren't handled;
- each principle: where does the build fall short of it?

Write each candidate as one line: what it is, which outcome or principle it serves, and an
effort estimate.

### 2. Alignment test

Every line must be true, or the candidate becomes a suggestion in the report instead:

- [ ] Serves a named *Good looks like* or *Fails if* outcome, or a named principle.
- [ ] Fits the Ambition (no social, multi-user, scale or monetization work on a personal
      tool unless the North Star says so).
- [ ] Breaks no non-goal and no must-not.
- [ ] Crosses no one-way door (see `SKILL.md` rule 4).
- [ ] Reversible and isolated: lands in its own commit, and removing it breaks nothing
      else.
- [ ] Fits the remaining budget in count and effort.
- [ ] Would the user's own calibration answers allow it? A "no" on a similar example
      settles it as no.

### 3. Proxy vote

Start 3 independent subagents. Give each only `CHARTER.md`, the calibration examples and
the candidate (never your reasoning for it). Ask: *Would this user want this built, given
their goals and answers? yes, no or unsure, with one sentence why.*

- 3 yes: build it.
- Any no: don't. Log it as a suggestion with the reason.
- Otherwise (an unsure, no no): don't. Log it as a suggestion.

Without subagents, vote inline as three deliberately different readers (one skeptical of
any new feature), say so in the report, and count each addition double against the budget.

### 4. Build, check, record

Build the passing candidate in its own commit, add a check for it, re-run every
must-have's check (an addition that breaks a must-have is reverted), and log it under
Added by Intent with the outcome it serves and the vote.

### 5. Stop adding when

- the budget's count or effort is spent;
- no candidate passes the alignment test and the vote;
- two candidates in a row were reverted for breaking checks.

## Stop conditions

Defaults; the charter may add more. On any of these, stop building, leave the project in
its last passing state, and write the report with a precise ask:

1. A needed credential, account, payment or human-only prerequisite is missing and the
   charter has no fallback.
2. A one-way decision is forced and no reversible path meets the must-have.
3. An action would delete or overwrite data outside the project, or anything the user
   didn't create for this project.
4. A must-have still fails after the retry and the alternative approach.
5. The checks can't run in this environment (no runtime, no browser, no network the
   check needs).
6. The work would publish anything outward (deploy, post, push to `main`, send email)
   beyond what the charter allows.

Everything else is a decision, not a stop.

## Final check and report

Before reporting done, run every acceptance command in the charter from a clean state and
paste the real output. Then write `INTENT-REPORT.md` from `templates/report.md`:

- **Built:** each must-have with its check and result.
- **Added by Intent:** each addition, the outcome or principle it serves, the vote, its
  commit and how to remove it.
- **Decisions I made:** the decision log, grouped by which rule settled each one.
- **Suggestions not built:** candidates that failed the test or the vote, and why.
- **Needs you:** stop conditions hit or fallbacks used, each with the exact ask.
- **Check results:** the final run's output.

The user's corrections to the report go into the ledger and calibration for the next run:
every addition they remove is a new "no" example, every suggestion they want is a new
"yes".
