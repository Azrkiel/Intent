EXTRACT = """Extract only new intent or explicit corrections from the latest user utterance.
The application owns item IDs. Return additions and updates, never rewrite the ledger.
Every confirmed item needs an EXACT verbatim substring from the latest utterance in source.
No quote means inferred, never confirmed. Do not silently infer core flows or success criteria.
An explicit requirement or decision stated by the user is confirmed when supported by that exact quote.
Extract each independently actionable clause separately; do not combine access, behavior, persistence,
and failure handling into one item. An explicit "Only me, without an account" answers the access slot.
An existing inferred item is not settled evidence. If the latest utterance explicitly confirms it,
update its existing id to confirmed with a source from this utterance; do not skip it as already known.
Use slots only for these meanings: goal=what to build, core-flow=main user action sequence,
data=what persists and where, access=who can use or see it, non-goals=explicit scope exclusions,
success-criterion=an observable test of success. A user/persona is not an access policy.
An answer can resolve a prior contradiction: update the affected items, don't leave stale facts.
If the user answers the active question, set answers_question to its id and record the decision
with their exact words. For unrelated remarks, leave answers_question null.
When correcting an earlier decision, update its existing id with the new text and source.
Never derive evidence from assistant questions; source must come from the latest user text.
"""

LENS_DESCRIPTIONS = {
    "data": "Data & persistence: what is stored, where, how long, and how it syncs.",
    "identity": "Identity & access: who uses it, accounts, ownership and visibility.",
    "behaviour": "Behaviour words: ambiguous automatic, smart, fast and simple behaviours.",
    "contradictions": "Contradictions: requirements whose implementations need reconciliation, "
    "such as cross-device persistence without an identity mechanism.",
    "edges": "Edges & failure: empty states, errors, offline and realistic scale.",
    "done-ness": "Done-ness: observable success criteria and the first thing the user checks.",
}


def critic_prompt(lens: str) -> str:
    return f"""You are the {lens} reviewer for a software idea.
{LENS_DESCRIPTIONS[lens]}
The ledger is the source of truth. Find gaps ONLY within your lens.
Return at most 3 candidates; use lens='{lens}'. Each needs 2-3 concrete plausible options
and a code_diff naming concrete files, tables, services, APIs or libraries that differ.
If the options build the same code, propose nothing. divergence=1 means discard.
Score divergence, uncertainty, cost_to_change from 1-3; impact is their product.
Target only existing ledger IDs; when the entire slot is missing, targets may be empty.
Never restate a confirmed item as a question. Never repeat an answered question.
Respect explicit scope exclusions as settled. Do not propose variants of excluded features or
reopen an explicit behavior merely because it could have been implemented differently.
Do not propose cosmetic questions when a default will do. Mark slot if it fills a required slot.
When your lens has no remaining build-changing uncertainty, return candidates: [].
"""


RANK = """Rank these candidates using the counterfactual code changes, not verbal importance.
Use the supplied ledger and answer history to check whether the proposed uncertainty is already settled.
When a question repeats a confirmed answer, reopens an explicit exclusion, or only changes presentation,
set divergence=1 so it is dropped. Keep genuinely unresolved architecture-changing questions visible.
For each input id return scores divergence, uncertainty, cost_to_change, each 1-3.
divergence=1 means both answers produce essentially the same code and the question is dropped.
For divergence, use 3 for incompatible architectures or data models, 2 for meaningful behavior changes,
and 1 for cosmetic variants or a small local guard with an ordinary default.
For cost_to_change, use 1 for a local function, handler, validation rule, or label; 2 for changes across
module interfaces; and 3 for a database migration, authentication boundary, or external integration.
Do not score hypothetical extreme scale as architectural uncertainty without a relevant stated need.
Do not create questions, alter their text, invent ids or rank answered questions.
Consider unresolved architecture-changing uncertainty before polish.
"""

BASELINE = """Ask clarifying questions about this software idea before a coding agent builds it.
Use the ledger and question history. Return up to 3 questions with 2-3 concrete options each,
using the candidate schema. Name the code difference, relevant lens, existing target IDs,
and scores 1-3 for divergence, uncertainty, and cost to change later.
Do not repeat answered questions or ask about confirmed details.
"""

PLAYBACK = """Summarize the confirmed ledger in at most three short sentences for the user.
Start with the original goal and main user actions before describing recent edge-case details.
Preserve exact triggers, timing, and recovery conditions; never replace a required user action
with automatic recovery. Include the access policy, persistence, and explicit exclusions concisely.
Use the ledger's exact access wording; do not add sign-in, accounts, or identity assumptions.
Mention open tradeoffs honestly. Include no new requirements or implementation choices.
Use plain spoken language. The UI separately asks 'What did I get wrong?'.
"""

COMPILE = """Compile a build brief, with one requirement per line and exact supporting ledger_ids.
Use sections Goal, Users, Must have, Must NOT have, Data, Decisions, Done when, Undecided.
Include EVERY confirmed item, especially negative constraints and explicit decisions.
Do not expand scope, add features, choose technologies or invent acceptance tests.
Each line must be fully entailed by the cited ledger text, not just loosely related.
Inferred and open items are NOT requirements: label them Undecided and say choose the simplest
option and list the choice in the final summary. Never fill gaps silently.
"""

VERIFY = """Check the brief against the ledger in both directions.
Return rejected_line_indices (zero-based) for lines that add ANY unsupported requirement,
contradict a source, cite invalid IDs, or misrepresent inferred text as confirmed.
Return missing_ledger_ids for confirmed items not faithfully covered by the brief.
Do not approve a line merely because it has a citation: verify semantic entailment.
"""
