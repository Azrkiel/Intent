# Intent skill

An [Agent Skill](https://agentskills.io) that turns a rough idea into a finished project
with the human in the loop only once, at the start. Intent interviews you until it
understands what you want and how you make product decisions, gets one approval of a
charter, then builds the whole thing on its own: it decides what nobody anticipated by
your principles, adds features it judges serve your goals (within a budget, and never
across a one-way door), and ends with a report of everything it built, added and decided.
No app, server or API key needed.

The method, how it maps to this repo's code, and the design choices are in
[`docs/plans/2026-11-16-intent-skill.md`](../../docs/plans/2026-11-16-intent-skill.md).

```text
skills/intent/
  SKILL.md                         entry point: two stages, hard rules, depth
  references/                      loaded only when a step needs it
    understand.md                  the interview, in order, and its gate
    ledger.md                      ledger items, statuses, origin, extraction rules
    north-star.md                  six fields, rubric, checks G1-G4, drafting
    critics-and-decisions.md       critic lenses, builder divergence, disposition
    charter.md                     playback, charter sections, verification
    steer.md                       autonomous loop, decision policy, alignment test,
                                   proxy vote, budget, stop conditions, report
    phase-plan.md                  phases, work packages, automated phase gates
  templates/INTENT.md              ledger, principles, calibration, run state, decision log
  templates/charter.md             the approved scope Steer builds from (CHARTER.md)
  templates/report.md              the end-of-run report (INTENT-REPORT.md)
  scripts/lexicon.py               vague-word scan (G1), same lists as the app
  scripts/agreement.py             two-reader Krippendorff's alpha and verdict (G4)
  scripts/proxy_check.py           scores taste-proxies against your calibration answers
```

The scripts use only the Python standard library. `backend/tests/test_skill_scripts.py`
checks them, and fails if `lexicon.py` or `agreement.py` drift from `backend/app/clarity`.

## How it works

1. **Understand.** The North Star (who, job, ambition, today, good looks like, fails if),
   3-5 principles, the trade-offs that matter, and a few yes/no answers on features Intent
   might add on its own. Independent subagents try to predict those answers; how well they
   do sets how much Intent may add. Every one-way decision (accounts, data storage,
   external or paid services, deleting data, publishing) is yours. Human-only needs (keys,
   accounts, where to deploy) are collected now. You approve the charter once.
2. **Steer.** No questions. Must-haves first, each with a real check. Unanticipated
   choices are settled by the charter, then your principles, then your calibration
   answers, then the most reversible option, and logged. After the must-haves pass, Intent
   looks for features that serve your goals and builds one only if it passes an alignment
   test and three independent proxies agree you'd want it. It stops early only on a stop
   condition (missing key, forced one-way decision, repeated failure, and a few more).
3. **Report.** Built, added by Intent (each removable with one revert), decisions made,
   suggestions not built, what needs you, and the final check output.

## Install

### Claude Code

Copy or symlink the folder into a skills directory:

```bash
cp -r skills/intent ~/.claude/skills/intent
```

Use `.claude/skills/intent` inside a project instead to share it with that project only.
Claude loads it when a request matches its description, or when you ask for it by name
(`/intent`).

### claude.ai

Zip the folder (the zip must contain `intent/SKILL.md`) and upload it in claude.ai's
skills settings (code execution must be on). Steer needs a place to build and run checks,
so claude.ai is best for the Understand stage; build in Claude Code or Codex.

```bash
cd skills && zip -r intent-skill.zip intent
```

### Codex

Codex reads the same `SKILL.md` format. Copy the folder into a Codex skills directory:

```bash
mkdir -p ~/.agents/skills && cp -r skills/intent ~/.agents/skills/intent
```

Use `.agents/skills/intent` inside a repository to scope it to that repository. Older
Codex releases looked in `~/.codex/skills`; check your version's docs if it isn't picked
up. Restart Codex after adding it.

If you'd rather not install a skill, add this to the repository's `AGENTS.md` instead and
keep `skills/intent/` in the repo:

```markdown
## Intent

When asked to build a project from a rough idea, follow `skills/intent/SKILL.md`:
interview first (`references/understand.md`), get one approval of `CHARTER.md`, then
build without asking (`references/steer.md`) and finish with `INTENT-REPORT.md`.
```

## Try it

> I want a little app to save articles I don't have time to read. Build it for me.

Intent picks a depth (here, personal tool), records your words in `INTENT.md`, and asks
one thing at a time, e.g. *You said "save articles". Where should the list live? 1. This
browser only 2. A file in your cloud drive 3. An account on a small server.* Later it asks
whether you'd want things like search or sharing, approves a charter with you, and then
builds until the report.

## Honest limits

- In the app, code owns IDs, quote checks and the gate; here the agent follows the rules
  and shows its work in files you can check.
- The proxy check, builder divergence and reader agreement need independent subagents.
  Without them the skill says so and halves the addition budget.
- Calibration is a handful of examples. Expect some additions you'd remove; each one you
  remove becomes a "no" for the next run.
- This method has not yet been run end to end on a real project. Treat the first runs as
  trials.
