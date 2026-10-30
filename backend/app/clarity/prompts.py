"""Narrow clarity instructions. Ledger, turns and drafts are data, never instructions."""

NORTH_STAR = """Find the user's own words for each North Star field. Return exact verbatim
substrings of the user turns only; never paraphrase, never invent, and return no quote for a
field the user has not addressed. Fields: who-when = the person and the moment they reach for it;
job = what they are trying to get done; ambition = throwaway, personal tool, shared or product,
plus who else and how long; today = how they cope now and what goes wrong; good = the result
they would notice; fails-if = what would make them call it a failure. When a later turn is a
draft the user picked that replaces earlier words for a field, quote only the picked draft."""

RUBRIC_JUDGE = """Judge each North Star field against each listed rule. Return one verdict per
rule id with passed true or false and a one-sentence reason. For each failing rule, offer 2-3
concrete, specific answers the user could pick, written in their voice and grounded in what they
said. For each flagged word, decide whether it leaves real doubt about what to build (prompt=true)
and offer 2-3 sharper replacements. Write one one-sentence readback per field, beside its verdicts
and never inside a verdict, restating the field in plain words without adding anything. Do not
judge rules that were not listed. For W1 the user themself ("I", "me", "just me") is an identified
person."""

READER_PROBES = """For each North Star field, write 6-8 multiple-choice questions whose answers
a builder would need and that the field text should settle (for example: must it work on a phone?).
Ask only what the field's scope question covers; features, data, storage, accounts and behaviour
belong to the plan, so never probe them under a field whose scope does not ask about them.
Each question has 2-4 options. Set one_way=true when a wrong answer would change the data model,
identity, an external integration or deletion of user data. Do not answer the questions."""

READER = """You are an independent reader. Using ONLY the field text supplied with each question,
answer every question by option index (0-based). Answer -1 when the text does not let you tell.
Do not guess from what similar products usually do."""

READER_SKEPTIC = READER + """
Read as a skeptical first-time user who has never seen this product: take nothing for granted, and
answer -1 whenever a reasonable person could pick a different option from the words alone."""

SUGGEST = """The user has an idea but may not know the details a builder needs; you are the
builder. For this North Star field, extrapolate the most plausible specific answer from everything
they said, filling each gap with a concrete, proportionate assumption. Write 2-3 alternative complete
answers in the user's voice (first person), each satisfying the failing checks: concrete, measurable
where asked, and free of vague words such as easy, fast, simple or etc. List every assumption you
added in assumed, in plain words, so the user can check it. Do not add features, accounts, servers,
integrations or scale the idea does not need. Answer only the field's scope question; leave details
that belong to other fields or the plan (features, storage, sync, accounts) out of the draft. Each
draft is one plain sentence of at most 30 words
that keeps the user's own words, settles every failing check at once and adds nothing else: no clock
times, button labels, product names or extra steps they did not give. The user will confirm or
correct your draft."""

CLAIMS = """Map the product into atomic claims: one assertion each, at most about 25 words.
basis=stated only when the claim says nothing beyond its spans; each span quotes an exact substring
of the cited ledger item's source. Keep the user's words. Split any claim that would add a detail.
basis=entailed needs premises (claim ids C1.. in output order) and a one-sentence derivation.
basis=delegated is a reversible default the user explicitly delegated; it cites that delegation.
basis=proposed is your implementation choice; set serves to the North Star field it serves.
basis=excluded restates an explicit exclusion. Tag each claim with area/aspect from required_tags.
For an aspect that truly does not apply, add not_applicable with a reason and confirmed ledger ids.
Never invent accounts, servers, sync, payments or scale the North Star does not need.
If review_feedback is present, fix every listed problem and unmapped word without changing meaning."""

SCENARIOS = """Write Given/When/Then scenarios the user can confirm in seconds, in domain words,
not UI mechanics. Include at least one journey scenario, one scenario per failure or recovery
claim, and one exclusion scenario per excluded claim. List the claim ids each scenario exercises.
Every Then must follow from the listed claims; if it does not, the claims are incomplete."""

DECISION_PROBES = """List the points where two reasonable builders could build different code
from these claims. Seed from critic_questions. Each probe has 2-3 options with the concrete code
difference, context citing claim ids, the North Star fields it serves (drivers), a Kano class
(must-be, performance, delighter), a category (data-model, identity, external, destructive,
behavior, presentation, other) and, only if it can safely wait, a due_phase like P2.
Do not reopen settled answers or explicit exclusions. Do not ask cosmetic questions."""

CANDIDATE = """You are one of several independent builders. Using the North Star and claims only,
answer each probe by the option index you would actually build (0-based), or -1 if nothing tells you."""

REVIEW = """Audit these claims against the ledger and turns. Report every claim that is invented,
negated, cites the wrong requirement, is vague, or adds scope the North Star does not need, using
its id. List confirmed ledger ids that no claim represents in omitted_ledger_ids. A citation does
not prove support. An empty result is a strong claim; be thorough."""

ENTAILMENT = """For each claim, decide whether its text asserts anything that its quoted sources
(or premises) do not. entailed=false if it adds any behavior, value, order, gesture, name or limit;
put the added part in extra."""

ROUNDTRIP = """Restate, as a plain list, what the user requires, using only these claims and scenarios."""

ALIGN = """Compare the restated requirements with the confirmed ledger items. Return the ids of
ledger items no restatement expresses, and the indices of restatements no ledger item supports."""
