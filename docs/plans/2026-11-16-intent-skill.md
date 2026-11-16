# The framework behind Intent, and a plan to ship it as an Agent Skill

Date: 2026-11-16. Requested by Kevin: "break down what's the framework behind intent and
then just think about it... and then turn that into a plan... execute it afterwards."

## 1. What the framework is

Intent's code is an app, but underneath it is a method for turning a vague software idea
into a brief a coding agent can build without guessing. Stripped of the app, the method
has one principle and nine parts.

**Principle: ask only what would change the build, and never pass off a guess as the
user's word.** Everything else enforces one half of that sentence.

| # | Part | What it does | Where it lives in the repo |
| --- | --- | --- | --- |
| 1 | Intent Ledger | Typed entries (goal, user, feature, data, constraint, non-goal, decision, assumption, success-criterion, open-question) with a status. *Confirmed* only with an exact quote from the user's own turn; anything else is *inferred*. Six required slots: goal, core flow, data, access, non-goals, success criterion. | `backend/app/domain.py`, `prompts.EXTRACT` |
| 2 | North Star | Six fields that must each be specific: Who & when, Job, Ambition, Today, Good looks like, Fails if. Each has rubric rules (W1-W4, J1-J2, A1-A3, T1-T2, O1-O3, F1-F2). | `clarity/contracts.py`, spec `2026-10-29-clarity-v2.md` |
| 3 | Clarity checks | G1 vague-word lexicon (prompt once, "keep my wording" allowed); G2 low-precision flags go to a judge first; G3 one-sentence read-back; G4 two independent readers answer 6-8 probes and must agree (Krippendorff's alpha >= 0.80, no "cannot tell"). | `clarity/lexicon.py`, `clarity/prompts.py` |
| 4 | Propose and confirm | Never demand detail the user doesn't have. Draft the most plausible specific answer, list the assumptions filled in, offer 2-3 alternatives. Nothing is adopted until the user picks or edits it; a picked draft becomes their words, labeled as drafted. | spec §2.4, `prompts.SUGGEST` |
| 5 | Six critic lenses | Data, identity & access, behaviour words, contradictions, edges & failure, done-ness. Each proposes at most 3 questions with 2-3 options and a plain-words code difference. | `prompts.critic_prompt` |
| 6 | Decision ranking and disposition | v1: impact = divergence x uncertainty x cost-to-change (1-3 each); divergence 1 means drop. v2: sample several candidate builds, and every probe they disagree on becomes a decision; score = split x Kano importance x reversibility - repeat penalty. One-way doors (data model, identity, external integration, destroying data) are always asked; two-way doors with >= 70% builder agreement become "choices I made for you" with a veto; low-value ones stop. Each decision is a MADR-style record scored on six Decision Quality links (weakest link wins). | `prompts.RANK`, `clarity/decisions.py` |
| 7 | Product framework map | Eight areas with named aspects: purpose, journeys, structure, data, access, failure-recovery, verification, scope. Every entry cites ledger IDs and is *confirmed*, *proposal* or *unresolved*. Atomic claims carry a basis (stated, entailed, delegated, proposed, excluded); Given/When/Then scenarios cover a journey, each failure and each exclusion. An independent review, calibrated with planted defects (canaries), must catch what's wrong. | `framework.py`, `clarity/provenance.py`, `clarity/canary.py` |
| 8 | Gate, playback, approval | The build gate opens only when every slot is confirmed, there are no conflicts, no high-impact question is open, the North Star passes and every one-way decision is user-owned. A three-sentence playback ends with "What did I get wrong?". Any new utterance invalidates approval and the brief. | `domain.gate_for`, `clarity/gate.py`, `prompts.PLAYBACK` |
| 9 | Cited brief and phase plan | Sections Goal, Users, Must have, Must NOT have, Data, Decisions, Done when, Undecided; every line cites ledger IDs; a verifier checks both directions (no unsupported line, no missing confirmed item). Exported as `CLAUDE.md`. Then a phased plan: at most 4 phases, 2 work packages per phase, 3 tasks per package, with per-phase human review. | `prompts.COMPILE`, `prompts.VERIFY`, `planning/prompts.py` |

## 2. How the parts fit

```text
idea ─► ledger (quotes) ─► North Star fields ─► critics + decisions ─► framework map
          ▲                    │  propose/confirm      │ ask one-way,           │ claims,
          │                    │  G1-G4 checks         │ delegate two-way       │ scenarios,
          └──── every answer is a new turn ◄───────────┴────────────────────────┘ review
                                                                     │
                                       gate ─► playback ─► approval ─► cited brief ─► phase plan
```

The loop is: listen, record with quotes, find the one most build-changing gap, propose an
answer, let the user confirm or correct, repeat. The gate is what stops the loop.

## 3. Thinking it through: tensions and gaps

1. **The app gets its honesty from code, a skill can't.** In Intent, the orchestrator owns
   IDs, quote checks, scores and the gate; models only propose deltas. In a skill, the same
   model extracts, critiques, judges and reviews. The skill has to make the invariants
   checkable by the user instead: quotes shown verbatim, statuses visible, the gate as a
   checklist, and the ledger saved to a file the user can read.
2. **Independence is the expensive part.** G4 (two readers) and divergence-first decisions
   both depend on separate minds disagreeing. One model agreeing with itself proves little.
   Where the host can start subagents (Claude Code, Codex), the skill should use them for
   readers and candidate builds. Where it can't, it should run the checks inline and say
   they are weaker, never report an alpha it didn't compute.
3. **Two generations of the same idea.** v1 (six slots, critics, framework map) and v2
   (North Star, claims, divergence decisions, canaries) overlap. The skill should present
   one loop: North Star first, then ledger slots, then decisions, then the map.
4. **Rigor vs. fatigue.** v2 has no question cap, and research cited in the spec says
   answers degrade with fatigue. Propose-and-confirm is the answer: Intent does the work of
   drafting, the user only picks. The skill also needs a proportionality switch: a quick
   path for a throwaway script, the full path for a product.
5. **Scores are heuristics, not measurements.** Divergence x uncertainty x cost is useful
   for ordering questions, not as a truth. The skill keeps the scale and the drop rule
   (divergence 1 means don't ask) without pretending to precision.
6. **Exact quotes are easy in chat.** The user's message is right there. The skill should
   quote the user, never the assistant's question, and treat a picked draft as the user's
   words labeled "drafted".
7. **Persistence.** The app keeps SQLite sessions. A skill should keep `INTENT.md` (ledger,
   North Star, decisions) in the repo so a later session or another agent can resume, and
   any new user statement reopens approval.
8. **Codex parity.** Intent already exports `CLAUDE.md`; Codex reads `AGENTS.md`. The skill
   should write the brief to whichever file the target agent reads, and Codex can load the
   same `SKILL.md` folder.

## 4. Plan

1. Create `skills/intent/` as the canonical, host-neutral copy (no repo convention exists).
2. `SKILL.md`: a description that triggers on vague build requests ("I want an app that…",
   "spec this out", "turn my idea into a brief"), the one-principle summary, the loop, the
   hard rules, quick vs. full mode, and pointers to references.
3. `references/` loaded on demand: ledger, North Star and clarity checks, critics and
   decisions, framework map and review, gate/playback/brief, phase plan.
4. `templates/`: `INTENT.md` (ledger file) and `brief.md` (the `CLAUDE.md` / `AGENTS.md`
   brief).
5. `scripts/`: dependency-free ports of the deterministic parts, `lexicon.py` (G1 scan,
   same word lists as `backend/app/clarity/lexicon.py`) and `agreement.py` (nominal
   Krippendorff's alpha for two readers, plus the pass/ask/fail verdict).
6. `README.md` with install steps for Claude Code, claude.ai and Codex, plus an
   `AGENTS.md` snippet for Codex.
7. Check: frontmatter is valid, scripts run on fixtures from the spec (weak vs. passing
   wording, hand-computed alpha), paths in docs exist, `git diff --check`. Add
   `backend/tests/test_skill_scripts.py` so the copied word lists and alpha formula fail
   CI if they drift from `backend/app/clarity`.
8. Commit, push the branch and open a PR. Nothing here touches the app or its tests.

Defaults chosen without asking: folder `skills/intent/`, skill name `intent`, ledger file
name `INTENT.md`, alpha thresholds and lexicon copied unchanged from the app.

## 5. Revision, same day: from spec-taker to product owner

Kevin clarified the vision after reviewing the first version: Intent should understand
the user well enough that the agent needs no human input after the interview, steers on
its own, and adds features it judges serve the project's goals without asking. The first
version did the opposite on purpose (never add scope, never invent requirements, human
review between phases), so the skill was reworked:

| First version | Revised |
| --- | --- |
| Clarify, then hand over a brief | Two stages: **Understand** (the only one that asks) and **Steer** (builds to the end without asking) |
| "Never add features the user didn't ask for" | Additions allowed after must-haves pass, if they pass an alignment test (serve a North Star outcome or principle, fit the Ambition, break no non-goal, cross no one-way door, reversible, within budget) and a unanimous vote of 3 independent taste-proxies |
| Requirements only | Also principles, trade-offs and yes/no calibration examples, so the agent can decide as the user would |
| No measure of the agent's judgment | `scripts/proxy_check.py`: proxies predict held-out calibration answers; accuracy and false yeses set the addition budget |
| Human review between phases | Automated phase gates (acceptance commands), a decision policy for unanticipated choices, a decision log, stop conditions, and an end-of-run report |
| Brief written into `CLAUDE.md` / `AGENTS.md` | `CHARTER.md`, referenced with `@CHARTER.md` or one `AGENTS.md` line, plus `INTENT-REPORT.md` |
| Quick and full modes | Depth scales with the Ambition field |
| Framework map, Decision Quality links, calibrated map review | Removed as ceremony that resolves no decision; builder divergence kept as the test for "would the agent have to guess?" |

Kept: provenance on everything (the user's words, drafted, or Intent's own call, never
blurred), propose-and-confirm, one-way doors as the user's alone (and never crossed by an
addition), the North Star rubric and G1-G4 checks.

Unproven: no end-to-end run yet. The next step is to plan and build one small project
with no human after the charter, and count the additions and decisions the user would
have made differently.
