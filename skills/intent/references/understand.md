# Understand: the interview

This is the only stage where the user is asked anything, so it has to collect everything
Steer will need. Every question follows the propose-and-confirm shape in `SKILL.md`: one per
turn, 2-3 concrete options, a draft the user can pick, and "or tell me in your own words".
Record every answer in the ledger with its quote (`references/ledger.md`).

## Order

Work through these in order; skip what the depth table in `SKILL.md` doesn't require.

### 1. The idea, in their words

Extract each clause of the first message into the ledger. Don't ask anything yet that the
next steps will settle.

### 2. North Star (the compass)

Six fields: Who & when, Job, Ambition, Today, Good looks like, Fails if. See
`references/north-star.md`. These are what every later choice is judged against, so they
must be specific. *Good looks like* turns into acceptance checks; *Fails if* turns into
tests and into the first candidates for additions; *Ambition* caps how far you go.

### 3. Principles (how they decide)

Draft 3-5 product principles from what they've said, each one line, each a choice between
two good things, e.g.:

- "Never lose a saved article, even if that means a slower save."
- "Fewer features, each one finished, over many half-done ones."
- "Keyboard first; the mouse is a fallback."

Offer them as a set: *These are my guesses at how you'd decide; keep, edit or drop each.*
Principles the user keeps are `drafted`; ones they write are `user`.

### 4. Trade-offs

Ask only the pairs that matter for this project, as forced choices with a concrete example
of each side. Pick from:

| Pair | Example question |
| --- | --- |
| Polish vs. shipping speed | "Smooth animations and empty states, or the working core a day sooner?" |
| More features vs. simplicity | "Add tags and folders, or keep one list?" |
| Convention vs. novelty | "Look like apps you already use, or try a new interaction?" |
| Robustness vs. effort | "Handle offline and bad input everywhere, or only on the main path?" |
| Automation vs. control | "Do things for you (auto-tag, auto-archive), or only when you ask?" |
| Breadth vs. depth | "Cover more cases roughly, or the main case really well?" |

Record each answer as a principle-like rule in `INTENT.md`.

### 5. Calibration (teach your taste-proxy)

This is what makes adding features safe. Draft 3-8 candidate additions you might build on
your own (the count comes from the depth table). Make them span the range: a couple you
think they'd want, a couple you think they wouldn't (at least one that breaks the Ambition,
like accounts on a personal tool), and some borderline. Ask for a quick yes or no on each,
with an optional reason:

> If I had time left after the must-haves, would you want me to add these?
> 1. Search across saved articles (yes / no)
> 2. Sharing a list with friends (yes / no)
> 3. A reading-time estimate on each article (yes / no)
> ...

Store them in `INTENT.md` under Calibration. Reasons are gold: turn any reusable reason
into a principle.

**Check the proxy before trusting it.** Start 3 independent subagents. Give each only the
North Star, principles, trade-offs and half of the labeled calibration items; ask each to
predict yes or no for the other half. Swap halves and repeat. Save the user's answers and
the predictions as JSON and run:

```bash
python scripts/proxy_check.py user.json proxies.json
```

The verdict sets the addition budget: `trusted` keeps the budget the user chose,
`cautious` caps it at small, `untrusted` sets it to none. The costly error is a false yes
(most proxies say "yes" where the user said "no"): one makes the verdict at best
`cautious`, two make it `untrusted`. Turn every miss into a principle or an extra
calibration item before writing the charter.
Without subagents, say the check couldn't be run independently and use `cautious`.

### 6. Scope and one-way doors

- **Must-haves:** what has to exist for the project to be worth anything.
- **Non-goals:** explicit exclusions. They bind additions too.
- **One-way decisions:** run the critics and builder-divergence check in
  `references/critics-and-decisions.md`. Every one-way decision it finds is asked now.
  Two-way splits are settled by the principles and recorded as `intent` with the
  principle that settled them; ask only if the principles don't decide it.

### 7. Done when

For each must-have and each *Good looks like* outcome, agree an observable check, and say
how you'll run it (a test, a command, a script that drives the app). Draft them; the user
confirms the meaning, not the code. A must-have without a runnable check is not done.

### 8. What only a human can give

List and collect now: API keys and secrets, accounts to create, paid services, domains,
where (if anywhere) to deploy, and which machine or environment to build in. For each, the
user either provides it, or agrees a fallback (mock the service, run locally, skip deploy).
Write nothing secret into `INTENT.md` or `CHARTER.md`; record only that it's provided and
where it lives (e.g. an env var name).

### 9. Autonomy settings

Draft these and let the user adjust:

- **Addition budget:** none, small (up to 3 additions, up to 20% of effort), moderate (up
  to 6, up to 35%), or a number they give. Capped by the proxy check in step 5.
- **Stop conditions:** the defaults in `references/steer.md`, plus any of theirs.
- **Commit and branch policy:** e.g. one branch, one commit per must-have and per
  addition, never push to `main`.

## Gate: ready to write the charter

All of these must be true. If one isn't, name it and keep asking.

- [ ] Every North Star field the depth requires passes its rubric; every G1 flag was
      prompted once.
- [ ] Principles and trade-offs recorded (as the depth requires).
- [ ] Calibration answered, proxy check run (or marked not independent), budget set.
- [ ] No ledger item in `conflict`; must-haves and non-goals confirmed.
- [ ] Every one-way decision found so far is answered by the user.
- [ ] Independent builders agree on every probe that matters (see
      `references/critics-and-decisions.md`), or the remaining splits are settled by a
      principle.
- [ ] Every must-have and every *Good looks like* outcome has a runnable check.
- [ ] Every human-only prerequisite is provided or has an agreed fallback.

Then playback and charter: `references/charter.md`.

## Keep it short

The user isn't paid to be interviewed. Draft everything, ask one thing at a time, and
watch for fatigue (much shorter answers, two "you decide"s in a row). When you see it,
draft harder and let principles settle two-way questions. One-way decisions still need the
user.
