# The Intent Ledger

The ledger is the single source of truth for what the user said. Everything later (the
North Star, principles, decisions, calibration, the charter, Steer's log) cites ledger IDs.

## Item

| Field | Values |
| --- | --- |
| `id` | `L1`, `L2`, … assigned in order, never reused or renumbered |
| `type` | goal, user, feature, data, constraint, non-goal, decision, assumption, success-criterion, principle, open-question |
| `status` | `confirmed`, `inferred`, `open`, `conflict` |
| `slot` | optional: goal, core-flow, data, access, non-goals, success-criterion |
| `text` | the requirement in plain words |
| `source` | exact quote from the user's turn (required for `confirmed`) |
| `turn` | which user message it came from |

## Statuses

- **confirmed**: the user said it; `source` is a verbatim substring of their message. A
  draft they picked is their words too; mark the source `(drafted)`.
- **inferred**: your reading of what they probably mean. Useful, never a requirement.
- **open**: a known unanswered question.
- **conflict**: two items can't both be built (e.g. "works across my devices" with "no
  accounts and no server" and no sync mechanism). A conflict blocks the gate.

## Origin

Separate from status, everything downstream of the ledger carries an origin:

- `user`: the user's own words, quoted.
- `drafted`: a draft or option the user picked or edited; their words now, marked so.
- `intent`: a choice Intent made (a principle-settled decision, a Steer decision, an
  added feature). It always names the North Star field, principle or calibration example
  it rests on, and it is never written up as something the user said.

## The six slots

Each should hold at least one confirmed item before the charter is written; the depth
table in `SKILL.md` decides how strictly.

| Slot | Means | Not this |
| --- | --- | --- |
| goal | what to build | a feature list |
| core-flow | the main sequence of user actions | the goal restated |
| data | what persists, where, for how long | the UI |
| access | who can use or see it | a persona (a persona is not an access policy) |
| non-goals | explicit scope exclusions | things you assume are out |
| success-criterion | an observable test of success | "works well" |

"Only me, without an account" is a complete access answer.

## Extraction rules

1. Record only new intent or explicit corrections from the latest message.
2. Split each independently actionable clause; don't merge access, behaviour,
   persistence and failure handling into one item.
3. Never derive evidence from your own questions; the quote must come from the user.
4. If the user explicitly confirms an inferred item, update that item to confirmed with a
   quote from this message instead of adding a duplicate.
5. A correction updates the existing item's text and source; it doesn't add a new one.
6. When an answer resolves a conflict, update every affected item; leave nothing stale.
7. When the user answers the active question, record the decision with their exact words.
8. Don't silently infer a core flow or success criterion. Ask, or draft and confirm.

## File format

Keep the ledger in `INTENT.md` (see `templates/INTENT.md`) as a table so the user can
read and edit it. If the user edits the file, treat their edit as a new turn.
