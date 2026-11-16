# Intent skill

An [Agent Skill](https://agentskills.io) that brings Intent's clarification method to any
coding agent: keep a quoted Intent Ledger, ask one build-changing question at a time,
draft answers for the user to confirm, and write a cited build brief only after a gate
passes. No app, server or API key needed.

The method, how it maps to this repo's code, and the design choices are in
[`docs/plans/2026-11-16-intent-skill.md`](../../docs/plans/2026-11-16-intent-skill.md).

```text
skills/intent/
  SKILL.md                         entry point: rules, modes, the loop
  references/                      loaded only when a step needs it
    ledger.md                      items, statuses, slots, extraction rules
    north-star.md                  six fields, rubric, checks G1-G4, drafting
    critics-and-decisions.md       six lenses, scoring, divergence, disposition
    framework-map.md               eight areas, claims, scenarios, calibrated review
    gate-playback-brief.md         gate checklist, playback, cited brief
    phase-plan.md                  phases, work packages, handoff
  templates/INTENT.md              the ledger file kept in the user's project
  templates/brief.md               the CLAUDE.md / AGENTS.md brief
  scripts/lexicon.py               vague-word scan (G1), same lists as the app
  scripts/agreement.py             two-reader Krippendorff's alpha and verdict (G4)
```

The scripts use only the Python standard library. `backend/tests/test_skill_scripts.py`
fails if they drift from `backend/app/clarity`.

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
skills settings (code execution must be on):

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
## Clarify before building

When a request to build something is vague or underspecified, follow
`skills/intent/SKILL.md` before writing code: keep `INTENT.md` as a quoted ledger, ask one
build-changing question at a time with 2-3 options, and write the cited brief to
`AGENTS.md` only after the gate in `skills/intent/references/gate-playback-brief.md`
passes and the user approves the playback.
```

## Try it

> I want a little app to save articles I don't have time to read.

The skill picks quick or full mode, records your words in `INTENT.md`, then asks something
like: *You said "save articles". Where should the list live? 1. This browser only 2. A file
in your cloud drive 3. An account on a small server.*

## Honest limits

- In the app, code owns IDs, quote checks and the gate; here the agent follows the rules
  and shows its work so you can check it.
- Reader agreement (G4), divergence across candidate builds and the calibrated review need
  independent readers. The skill uses subagents where the host has them and says when a
  check ran inline instead.
