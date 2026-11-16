# Gate, playback and brief

## Gate checklist

The gate opens only when every applicable line is true. Show it as a short checklist when
the user asks how close they are, or before playback.

**Both modes**

- [ ] All six slots (goal, core-flow, data, access, non-goals, success-criterion) hold a
      confirmed item with a quote.
- [ ] No ledger item is in `conflict`.
- [ ] No open critic question with impact >= 12.
- [ ] Every critic lens finished (none skipped because of an error).

**Full mode adds**

- [ ] Every North Star field passes its rubric, G3 and G4, and every G1 flag was prompted
      once (sharpened or kept).
- [ ] Every one-way decision is owned by the user, with all six Decision Quality links.
- [ ] No open decision scores at or above the stop threshold.
- [ ] Every deferred decision has a due phase.
- [ ] The framework map covers every aspect and every confirmed item, its independent
      review has no open issues, and that review was calibrated.
- [ ] Scenarios are written.

If something isn't met, name it in one line and return to questioning. Never pass a check
because you ran out of time or budget; say the gate is still closed.

## Playback

At most three short, plain sentences for the user:

1. The original goal and the main user actions.
2. Access policy, persistence and explicit exclusions, in the ledger's own wording (don't
   add sign-in or accounts that aren't there).
3. Open trade-offs, honestly.

Preserve exact triggers, timing and recovery conditions; never replace a required user
action with automatic recovery. Add no new requirements or implementation choices. Then
ask: **"What did I get wrong?"**

Show **"What I filled in for you"** beside it: proposals and "Choices I made for you", each
with a one-line veto. Approval covers these; a veto or correction reopens them.

Approval must be explicit ("yes", "approved", "looks right"). Any later statement from the
user invalidates it.

## Brief

Compile only after approval. Use `templates/brief.md`.

Sections, in order: **Goal, Users, Must have, Must NOT have, Data, Decisions, Done when,
Undecided.** In full mode add **North Star**, **Choices made for you** and **Done when
(approved scenarios)**.

Rules:

- One requirement per line, each ending with its ledger IDs in brackets: `[L3, L7]`.
- Include **every** confirmed item, especially negative constraints and explicit decisions.
- Each line must be fully entailed by the cited text, not just related to it.
- Don't expand scope, add features, choose technologies or invent acceptance tests.
- Inferred and open items are not requirements. Put them under **Undecided** with: "Choose
  the simplest option and list the choice in your final summary."

### Verify both ways

Before handing it over, re-read the brief against the ledger (ideally with a fresh
subagent that sees only the two):

- Reject any line that adds an unsupported requirement, contradicts its source, cites an
  invalid ID, or presents inferred text as confirmed.
- List confirmed items the brief doesn't faithfully cover, and add them verbatim from the
  ledger.

A citation alone doesn't prove support; check the meaning.

### Where it goes

- Claude Code reads `CLAUDE.md`; Codex and most other agents read `AGENTS.md`. Write to the
  one the repo already uses; if neither exists, ask once (default `CLAUDE.md` in Claude
  Code, `AGENTS.md` in Codex). If the file already has content, add the brief as a
  `## Build brief` section rather than overwriting.
- Keep `INTENT.md` alongside it so a later session can resume or reopen questions.
