# Playback and charter

The charter is the last thing the user approves. After that, Steer runs on it alone, so it
must answer every question Steer is allowed to answer and say where Steer must stop.

## Playback

At most four short, plain sentences:

1. What gets built and for whom, in the North Star's words.
2. The must-haves, the explicit non-goals, and the one-way decisions, in the ledger's own
   wording (don't add sign-in or accounts that aren't there).
3. How you'll steer: the principles in a phrase each, and the addition budget.
4. What will make you stop and come back.

Then ask: **"What did I get wrong?"** Beside it, show "Choices I made for you" (two-way
decisions settled by a principle) with a one-line veto each.

Approval must be explicit ("yes", "approved", "go"). Tell the user that after approval you
won't ask anything else until the report, unless a stop condition hits.

## Charter sections

Use `templates/charter.md`. Every line cites ledger, decision or calibration IDs and its
origin (`user`, `drafted` or `intent`).

1. **North Star:** the six fields as approved.
2. **Principles and trade-offs:** each as a one-line rule Steer can apply.
3. **Must have:** one requirement per line, each with its acceptance check.
4. **Must NOT have:** non-goals and must-nots. They bind additions too.
5. **Decisions:** every one-way decision with the user's answer; two-way ones settled
   during Understand with the rule that settled them.
6. **Calibration:** the labeled examples, so proxies and the decision policy can cite them.
7. **Autonomy:** addition budget (as capped by the proxy check), commit and branch policy,
   stop conditions.
8. **Environment and prerequisites:** where to build, how to run checks, which secrets are
   provided and where they live (names only, never values), and agreed fallbacks.
9. **Done when:** the acceptance commands that must all pass, and what they show.

Rules:

- Include **every** confirmed ledger item, especially negative constraints and explicit
  decisions.
- Each requirement line must be fully entailed by the cited text, not just related to it.
- Inferred items are not requirements. They go to the decision policy, where principles
  decide them and Steer logs them.

## Verify it both ways

Before asking for approval, have a fresh subagent that sees only the ledger, the user's
messages and the charter check it (inline if no subagents, and say so):

- Reject any line that adds an unsupported requirement, contradicts its source, cites an
  invalid ID, or labels an `intent` item as `user`.
- List confirmed items the charter doesn't faithfully cover, and add them.
- Flag any must-have without a runnable check, and any human-only prerequisite without a
  fallback.

A citation alone doesn't prove support; check the meaning.

## Where it goes

Write `CHARTER.md` in the project root and reference it from the agent's instructions
file rather than pasting it: `@CHARTER.md` in `CLAUDE.md` (Claude Code), or a line "Read
CHARTER.md before any work; it is the approved scope" in `AGENTS.md` (Codex). Keep
`INTENT.md` alongside so a later session can resume.
