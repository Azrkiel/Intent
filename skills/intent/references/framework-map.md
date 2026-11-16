# Product framework map (full mode)

The map shows the whole product is specified, not just that six slots are occupied.

## Eight areas and their aspects

| Area | Aspects |
| --- | --- |
| purpose | problem, users, outcome |
| journeys | entry, actions, completion |
| structure | components, boundaries, dependencies |
| data | entities, storage, lifecycle |
| access | actors, permissions |
| failure-recovery | validation, failure, recovery |
| verification | observable-behavior, checks |
| scope | included, excluded |

Every aspect needs at least one entry that is not `unresolved`, or an explicit
"not applicable" with the reason and the confirmed ledger IDs that support it (e.g. access
→ permissions: not applicable, "only me" L4).

## Entries

Each entry: area, aspect, text, cited ledger IDs, and a status:

- **confirmed:** fully supported by confirmed ledger text.
- **proposal:** your implementation choice (technology, UX, test). Never a requirement.
- **unresolved:** a product decision the user must make; it also becomes a question.

Every confirmed ledger item must appear in at least one confirmed entry.

Describe the actual product, not a template. A journey runs from entry through ordered
actions and state changes to an observable outcome, with inputs, outputs, the saved or
computed result and its failure paths. A component says what it consumes, what it produces
and what it connects to. Keep architecture proportional to the Ambition field.

Banned filler: "simple flow", "save stuff", "handle errors", "works well", or a list of
feature names with no behaviour.

## Claims (optional finer grain)

For high-stakes products, break the map into atomic claims of about 25 words, each with a
basis:

| Basis | Meaning |
| --- | --- |
| stated | says nothing beyond its quoted spans |
| entailed | follows from listed premise claims, with a one-sentence derivation |
| delegated | a reversible default the user explicitly handed you; cites that hand-off |
| proposed | your choice; name the North Star field it serves |
| excluded | restates an explicit exclusion |

Every content word of each confirmed ledger quote should be covered by some claim. If a
word isn't, map it or say why it doesn't matter.

## Scenarios

Write Given/When/Then scenarios the user can confirm in seconds, in domain words, not UI
mechanics:

- at least one journey scenario;
- one per failure or recovery claim;
- one per exclusion.

Each lists the claims it exercises, and every Then must follow from them. In full mode the
user approves scenarios (plus "Choices I made for you") instead of the prose playback.

## Independent review

The map is a proposal to challenge, not an authority. Review it with a fresh reader (a
subagent given the ledger, the user's turns and the map, and none of your reasoning):

- every entry and all eight areas, each exactly once;
- specificity, faithfulness to cited meaning, internal consistency, all paths connected;
- omitted confirmed requirements, invented requirements, negated or miscited ones, scope
  creep, vague entries;
- tests are concrete proposals grounded in required behaviour.

Each defect becomes an issue with its area; each missing user decision becomes a question
with 2-3 options and the code difference.

**Calibrate the reviewer.** An empty review must be earned. Before trusting "no issues",
plant a few known defects in a copy (add an invented feature to one claim, negate
another, cite the wrong ledger item, replace one with "handles this appropriately and works
well", insert "add accounts and cloud sync" as scope creep). The reviewer must catch every
planted invention, negation, miscitation and scope creep (the costly kinds), and at least
80% of all planted defects. If it doesn't, its
clean verdict doesn't count; say so.

Any new user statement makes the map stale; re-check it against the current ledger before
the gate.
