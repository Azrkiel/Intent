# Charter: <working title>

Approved by the user on <date>. This is the whole scope. Build all of it without asking;
decide anything it doesn't cover with the decision policy below, log every decision in
INTENT.md, and stop only on a stop condition. Origins: `user` = the user's words,
`drafted` = a draft the user picked, `intent` = Intent's own call.

## North Star
- Who & when: <text> [L2, drafted]
- Job: <text> [L1, user]
- Ambition: <text> [L3, user]
- Today: <text> [L5, user]
- Good looks like: <text> [L6, drafted]
- Fails if: <text> [L7, user]

## Principles and trade-offs
- P1 <rule> [L4, user]
- P2 <rule> [L9, drafted]

## Must have
- <requirement> [L8, user] · check: `<command>` shows <result>

## Must NOT have
- <non-goal or must-not> [L10, user]
- No accounts, servers, paid services or new data stores beyond the decisions below.

## Decisions
- D1 <question> → <answer> (because <driver>) [L11, user] · one-way
- D2 <question> → <answer> (because P2) [intent] · two-way, veto offered at playback

## Calibration
- K1 <candidate addition>: yes ("<reason>")
- K2 <candidate addition>: no ("<reason>")

## Autonomy
- Addition budget: <none / small: up to 3 and 20% of effort / moderate / N> (proxy check: <verdict>)
- Additions only after every must-have passes; each in its own commit; each must pass the
  alignment test and a unanimous proxy vote (skills/intent/references/steer.md).
- Decision policy: charter → principle → calibration → most reversible two-way option →
  reversible path around a one-way door, else stop.
- Commits and branches: <policy, e.g. branch intent/build, never push to main>
- Stop conditions: missing human-only prerequisite with no fallback; forced one-way
  decision with no reversible path; touching data outside the project; a must-have still
  failing after retries and one alternative; checks can't run here; publishing outward
  beyond this charter. <plus the user's own>

## Environment and prerequisites
- Build in: <path / machine>. Run checks with: `<command>`.
- <secret>: provided as env `NAME` (value not stored here) · <service>: fallback <mock>

## Done when
- `<command>` passes: <what it shows> [L6]
- Given <context>, when <action>, then <observable result> [L7] · check: `<command>`
