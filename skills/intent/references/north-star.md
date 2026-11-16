# North Star and clarity checks

Six fields describe why the thing exists. They are Steer's compass: every unanticipated
decision and every feature Intent adds on its own is judged against them. Settle them
first, in this order (the depth table in `SKILL.md` says which are required):

1. **Who & when** 2. **Job** 3. **Ambition** 4. **Today** 5. **Good looks like** 6. **Fails if**

A field passes only when all of its rubric rules and all applicable checks (G1-G4) pass.
There is no question cap, but every follow-up is a draft for the user to pick, so the user
never has to invent detail.

## Rubric

| Field | Rules (all required) | Weak → passing |
| --- | --- | --- |
| Who & when | **W1** names a person or group the user can identify ("I" counts for a personal tool), not "users" or "people". **W2** an observable trigger moment ("When…"). **W3** device or place. **W4** frequency. | "people who read" → "me, on my laptop, several times a day when I find an article I can't read now" |
| Job | **J1** one verb and one object, no "and"/"or". **J2** names no feature or technology. | "manage articles and stuff" → "save an article to read later" |
| Ambition | **A1** throwaway / personal tool / shared with a few people / product. **A2** who else uses it. **A3** how long it should last. | "just an app" → "personal tool, only me, used for months" |
| Today | **T1** the current workaround. **T2** one concrete pain with it. | "it's messy" → "I leave tabs open and lose them when Chrome restarts" |
| Good looks like | **O1** direction, measure, object and context. **O2** (prompt once, not blocking) a number with a unit. **O3** names no feature. | "fast and easy" → "find a saved article in under 10 seconds" |
| Fails if | **F1** an observable if/then failure. **F2** specific to this product. | "if it's buggy" → "if a saved link disappears after reload" |

W1, J1, J2 and O3 forbid wording, so only a rewrite fixes them. The others ask for
something to be said, so an added clause can satisfy them.

When you judge a rule, name the rule ID in your verdict. A verdict without a rule ID
doesn't count.

## G1: vague words (deterministic, not blocking)

Run `python scripts/lexicon.py "<field text>"`. It flags subjective words ("easy",
"intuitive"), vague words ("fast", "some", "stuff"), escape clauses ("if possible", "as
needed"), open endings ("etc", "and so on"), absolutes ("always", "every"), comparatives,
pronouns and negations.

- Prompt each flagged word **once**: quote it and offer 2-3 sharper options plus "keep my
  wording". Kept wording is recorded as `kept by user` and satisfies G1.
- Kept vague words still have to pass the rubric and G4.

## G2: flag precision

Subjective, vague, escape and open-ended flags are reliable; prompt them directly.
Absolutes, comparatives, pronouns and negations are often false alarms; decide first, with
a one-line reason, whether the word leaves real doubt about what to build. Only prompt if
it does.

## G3: read-back

Restate the field in one plain sentence, adding nothing. The user confirms or corrects; a
correction is a new turn and reruns the checks. A field written entirely from a draft the
user just picked skips G3 (they've confirmed that exact text), but not the rubric or G4.

## G4: reader agreement (product depth, optional otherwise)

Two independent readers, given only the field text, answer the same 6-8 multiple-choice
probes a builder would need settled (e.g. "Must it work on a phone? yes / no / cannot
tell"). Probes stay inside the field's scope: features, storage and accounts belong to the
plan, not the North Star. Mark a probe **one-way** if a wrong answer would change the data
model, identity, an external integration or deletion of user data.

- **How to get independent readers:** in Claude Code, start two subagents with only the
  field text and the probes; make one a skeptical first-time reader who answers "cannot
  tell" whenever a reasonable person could pick differently. In Codex, use two separate
  sub-tasks the same way. With no subagents, answer inline as two deliberately different
  readers and say the check was inline.
- Compute agreement with `python scripts/agreement.py reader_a.json reader_b.json` (lists
  of option indexes, `-1` for cannot tell; optional `--one-way` probe indexes).
- **Pass:** alpha >= 0.80, no "cannot tell", no disagreement on a one-way probe.
- **Ask one follow-up:** 0.667 <= alpha < 0.80; ask about the disagreeing probe.
- **Fail:** alpha < 0.667, any "cannot tell", or any one-way disagreement; the probe
  becomes the follow-up.

## Drafting (propose and confirm)

For every missing, vague or failing field:

1. Extrapolate the most plausible specific answer from everything the user said.
2. Fill each gap with a concrete, proportionate assumption and list the assumptions.
3. Offer 2-3 alternative drafts, each one plain first-person sentence of at most 30 words,
   free of lexicon words, settling every failing rule at once, answering only this field.
4. Add no features, accounts, servers, sync, clock times, button labels or product names
   the user didn't give. If the user's wording mostly works, keep it word for word and add
   one clause.
5. Offer "keep my wording" for vague-word and O2 prompts.

Format: *My best guess from what you told me: "…". I filled in: … Does that fit?* then the
alternatives.

Watch for fatigue: answers getting much shorter, two "you decide"s in a row, repeated
one-word replies. When you see it, lean harder on drafts and defaults for two-way choices;
one-way decisions still need the user.
