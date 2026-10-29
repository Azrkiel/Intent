# Clarity v2 proposal: from filled categories to determined behavior

Status: **proposal.** §11 decisions, North Star rubrics and the decision framework
are now specified in [clarity v2](../specs/2026-10-29-clarity-v2.md). No code changed. Builds on the
[framework-backed clarity spec](../specs/2026-10-29-framework-clarity.md) and the
failed live qualification recorded in
[the framework plan](2026-10-29-framework-clarity.md).

## 1. Why the current framework passes bad maps

The live component check (`.data/live-check/qualification-20261029-182856/`) is
the best evidence available: structural validation passed, the reviewer returned
no issues, and a human found eight defects. Each defect traces to a structural
cause, not to a prompt that needs more adjectives.

| # | Root cause | Observed symptom |
| --- | --- | --- |
| R1 | Completeness is measured by occupied categories (21 aspects), not by whether behavior is determined. The six-slot problem moved up one level. | The vague idea got a full map with invented task management, cloud sync and automation. The gate demands every aspect, so the mapper fills them. |
| R2 | Provenance is per entry and per ledger ID. One invented clause inherits `confirmed` from its neighbours, and one cited ID counts as full coverage. | Swipe deletion, disabled Add and unread-then-read ordering marked confirmed. "Allow duplicates" dropped while L6 counted as covered. |
| R3 | `confirmed` is a model-written label. The app checks only that the cited items are confirmed, not that the text says only what they say. | The `readingQueue` key, plain JSON and the no-framework choice were labeled confirmed. |
| R4 | The reviewer is the same model family with the same context, and an empty issue list costs nothing and cannot be checked. | Zero issues on a map with eight defects. Also zero issues on the vague map's invented scope. |
| R5 | No "why" layer. Proposals have no principle to follow, so the mapper falls back to a generic app template. "Use reversible defaults" had no limit. | Invented scope on vague input. Technical defaults promoted to user requirements. |
| R6 | Users approve a prose playback, and people skim prose. Concrete examples are where wrong guesses become visible. | The Reset wording did not clearly preserve "wait for my click", and nothing in the flow showed the user that difference. |

Lesson: every check that passed was a check of form (areas present, IDs valid,
addresses reviewed). None checked meaning, and the one meaning check (the
reviewer) could not fail in any measurable way.

## 2. What "clear" means

> Intent is clear when a competent builder who reads only the framework would make
> the same consequential choices the user would, and the user recognizes their
> product in concrete examples of it.

That gives three testable properties, used throughout this proposal:

1. **Faithful:** nothing is presented as the user's requirement unless they said
   it, and nothing they said is lost. (R2, R3)
2. **Determined:** every choice where two reasonable builds would diverge is
   either decided by the user, delegated with a stated default, or excluded.
   (R1, R5)
3. **Recognizable:** the user has confirmed concrete scenarios, not only a
   summary. (R6)

A clarity check that cannot fail one of these properties on real input is not a
check. That includes R4.

## 3. Layers of intent: the product-vision idea, made operational

A product vision separates a stable "why" (target customer, need, value,
difference from alternatives, success measures) from a roadmap that changes
often. Intent needs the same split. Each layer has a different owner and a
different rate of change.

| Layer | Question | Owner | Volatility | Evidence required |
| --- | --- | --- | --- | --- |
| **North Star** | Why does this exist, for whom, in what situation? | User | Stable | Quote or confirmed in playback |
| **Commitments** | What must it do and not do? | User | Changes only by correction | Exact quote span |
| **Decisions** | Where could builds diverge, and who chose? | User, or explicitly delegated | Per decision | Answer quote or delegation record |
| **Proposals** | How will it be built? | Builder | Cheap to change, user can veto | Must name the North Star clause it serves |
| **Scenarios** | What will I see when I use it? | Shared | Derived from the layers above | User confirmation |

A correction at one layer invalidates only what depends on it. Proposals can be
regenerated freely; commitments cannot be changed by a model.

### 3.1 The North Star (Intent's product vision)

Six short fields, each quote-backed or explicitly marked inferred and shown for
confirmation in playback:

- **Who and when:** the person and the situation that starts it. Not a persona;
  the trigger ("when I find an article on my laptop I have no time to read").
- **Job:** what they are trying to get done.
- **Today:** how they cope now. This shows the real pain and the baseline the
  product has to beat ("I leave 40 tabs open").
- **Good looks like:** the felt outcome, in their words.
- **Fails if:** what would disappoint them. People often state anti-goals more
  precisely than goals, and this is where hidden constraints appear.
- **Ambition:** throwaway / personal tool / shared with a few people / product.
  This sets how much architecture is appropriate (§5.3).

Statement form, adapted from a vision statement (who, what they accomplish, what
makes it different):
`When <situation>, <who> can <job> so that <outcome>, instead of <today>.`

**Why this is not filler:** the North Star is a decision rule. Every proposal
must name the clause it serves, and the builder uses the North Star to break ties
on choices nobody asked about. Example for the reading-queue fixture: with
ambition "personal tool" and fails-if "it becomes another thing to manage",
the builder can reject swipe gestures, grouping and extra controls without asking.
A proposal that serves no clause is scope creep by definition. That is the check
that blocks the vague map's invented cloud sync.

## 4. Atomic claims with computed provenance (fixes R2, R3)

Replace paragraph entries with **claims**: one assertion each, short (about 25
words or fewer), with an app-owned ID. Areas become tags on claims, not
containers that need filling.

```text
Claim
  id            app-owned, e.g. C7
  text          one assertion
  tags          area/aspect index, e.g. failure-recovery/validation
  basis         stated | entailed | delegated | proposed | excluded
  spans         stated: [{item_id, start, end}]  exact substrings of the item source
  premises      entailed: claim IDs + one-sentence derivation
  serves        proposed/delegated: North Star field
  reversibility 1 local | 2 cross-module | 3 data model, identity, external, destructive
```

Rules owned by the app (deterministic, no model calls):

- **Status is computed, never declared.** A claim is confirmed only if its basis is
  `stated` and every span is an exact substring of a confirmed ledger item's source.
  The model cannot write `confirmed`.
- **Quote tiling (omission check).** For every confirmed ledger item, the union of
  spans across all claims must cover every content word of its source (stopwords
  removed). Any gap becomes a blocker naming the exact missing words, for example
  `Map "allow duplicates" from L6`. This alone would have caught the dropped
  duplicate rule.
- **Novelty tripwire (addition check).** Content words in a stated claim that do not
  appear in its spans (after case and stem normalization) are flagged. The claim
  must be split, or the extra part relabeled `proposed`. This flags `swipe`,
  `readingQueue`, `disabled` and `JSON`. It is a heuristic, so it can only
  **downgrade** a claim, never upgrade one. Paraphrases will trip it; that is
  acceptable, because stated claims should stay in the user's words.
- **Entailed claims** need premises, and each one is checked individually (§7.1).
- **Delegation cannot confirm.** A "use reversible defaults" item (L11) authorizes
  `delegated` claims of reversibility 1. It never makes a technical choice a user
  requirement, and it never covers reversibility 2–3.

## 5. Decision register instead of "fill every aspect" (fixes R1, R5)

### 5.1 Decisions are the unit of clarity

A **decision** is a point where two plausible builds would produce different
code or behavior. The critics already produce these as questions. The register
combines them with mapper-found gaps and probe disagreements (§7.2):

```text
Decision
  question, options (2-3), code_diff
  owner          user | delegated | excluded
  resolution     answer quote | default claim ID | exclusion item ID
  cost_to_change 1-3 (existing ranker scale)
```

### 5.2 Ownership follows reversibility

- Cost 3 (data model, identity boundary, external integration, deleting or
  overwriting user data): **always user-owned.** It cannot be delegated.
- Cost 2: user-owned unless the user explicitly delegated that category.
- Cost 1: may be delegated. It appears in **"Choices I made for you"** with a
  one-click veto, which counts as a new utterance.

### 5.3 Aspects become discovery prompts

The 21 aspects stay as a checklist of where to look for decisions. An aspect may be
`not-applicable` with a citation to an exclusion or to the ambition level
("access/permissions: n/a, single user, no account (L2)"). Required aspects come
from ambition: a personal tool does not need access roles. This removes the
pressure to invent content in order to fill categories.

## 6. Scenarios as the shared language (fixes R6)

People catch errors in concrete examples that they miss in summaries, which is the
core idea of specification by example. Each framework includes Given/When/Then
scenarios:

- at least one per journey;
- one per failure or recovery commitment;
- one negative scenario per exclusion ("Given the app on a second device, Then
  nothing is shared or synced").

Each scenario lists the claims it exercises. App rules: every stated behavior claim
is exercised by at least one scenario; a scenario whose `Then` cannot be derived
from claims reveals an undecided point and becomes a decision.

**Playback becomes 3–6 scenarios plus the "Choices I made for you" list.** The user
approves those. The prose summary stays as a header. The Reset defect shows why:

> Given saved data is corrupt, When you open the app, Then it shows Reset and
> changes nothing until you click it.

A user can confirm or correct that sentence in seconds. The prose version hid the
ambiguity. Approved scenarios then become the acceptance checks passed to the
brief and the phase planner, so "done" is defined in the user's terms.

## 7. Verification that can fail (fixes R4)

### 7.1 Narrow checks instead of one broad reviewer

- **Entailment per stated or entailed claim.** Input: only the claim and its spans
  (or premises). Question: "Does the claim assert anything the source does not?"
  A narrow context makes additions hard to miss. Batch the claims into one Nano call.
- **Round-trip reconstruction.** A fresh call sees only the framework, not the
  ledger, and restates what the user required. The app aligns that restatement
  with confirmed items: an item that cannot be reconstructed is an omission, and an
  extra requirement in the restatement is an invention.

### 7.2 Prediction probes: measure determinacy directly

Generate 6–10 concrete situations from journeys, edges and critic lenses (for
example "two identical URLs are added", "the user opens the app with corrupt data
and doesn't click anything", "All filter with read and unread items: what order?").
Two isolated cheap calls answer from the framework alone, each with
`determined | had to guess`. A guess or a disagreement becomes a decision-register
entry. This replaces the critics' estimate of divergence with an observed one.

### 7.3 Canary calibration: an empty review must be earned

Before trusting "no issues", the app copies the map and plants `k` defects from
a catalogue of the observed failure types: an invented confirmed clause, a dropped
clause, a flipped negation, a wrong citation, scope creep. The reviewer receives
the mutated copy and does not know which defects were planted. The app knows the
ground truth, so:

- below the recall threshold (proposed: all canaries of reversibility 2–3, and at
  least 80% overall), the review is **untrusted** and the gate stays closed with
  `Framework review could not be verified`;
- findings that do not match a canary are real issues in the map;
- recall per model over time shows which reviewer model to route to, measured on
  the actual data.

This is mutation testing applied to the reviewer. It turns "no issues" from an
unfalsifiable answer into a measured result, and it fits inside the existing
review pass.

## 8. Gate and readout

The gate stays application-owned and fail-closed. It opens only when all of these
hold:

1. Current revision and source hash (unchanged).
2. Zero stated claims with unresolved novelty flags; zero failed entailment checks.
3. Complete quote tiling for every confirmed item.
4. Every cost-2/3 decision user-owned and resolved; no probe disagreement on them.
5. Every proposal names a North Star clause; required aspects mapped or `n/a` with
   a citation.
6. Canary recall met; round-trip finds no omission.
7. User approved the scenarios and the "Choices I made for you" list (existing
   explicit approval step).

Replace the aspect percentage with an honest readout:
`11 statements mapped · 0 words unmapped · 4 choices made for you · 1 decision needs you · 6 scenarios to confirm`.

## 9. Coverage of the observed defects

| Observed defect | Caught by | Model calls needed |
| --- | --- | --- |
| structure.2 plain JSON / no framework labeled confirmed | Novelty tripwire; delegation cannot confirm | None |
| data.1 `readingQueue` key labeled confirmed | Novelty tripwire | None |
| journeys.1 swipe deletion | Novelty tripwire; entailment | None / Nano |
| failure-recovery.0 disabled Add | Novelty tripwire; entailment | None / Nano |
| failure-recovery.0 / L6 "allow duplicates" dropped | Quote tiling | None |
| failure-recovery.2 Reset may not wait for click | Recovery scenario; "user doesn't click" probe | Nano |
| structure.0 unread-then-read ordering | Entailment; ordering probe becomes a decision | Nano |
| purpose.0 asserts exclusions from uncited items | Atomic claims with per-claim spans | None |
| Vague idea: invented sync and automation | Ambition-based aspects; proposals must serve the North Star | None |
| Reviewer reported nothing | Canary calibration | Within existing review |

Six of the ten are caught deterministically, with no new model calls and no
dependence on model judgment.

## 10. Rollout

Each phase is independently useful, and each one tightens the gate.

1. **Deterministic provenance:** claims, spans, computed status, quote tiling,
   novelty tripwire, delegation rule. Mapper schema change only. Biggest gain,
   no new calls. Regressions: the eight human findings as fixtures.
2. **North Star and decision register:** the six fields, ambition-based aspects,
   `n/a`, ownership by reversibility, "Choices I made for you".
3. **Scenarios:** generation, claim exercise rules, scenario playback and approval,
   scenarios passed to brief and planner as acceptance checks.
4. **Adversarial verification:** canaries in the existing review pass, batched
   entailment, round-trip, probes. All on Nano/Super within `SESSION_BUDGET_USD`.
5. **Evaluation and live requalification:** extend `backend/evals/fixtures.json`
   with framework gold labels (the reading-queue fixture and its eight findings,
   plus vague-input fixtures). Report invented-confirmed rate (target 0), clause
   omission rate, canary recall, probe agreement and human acceptance, with spend.
   Only a fresh full live interview with human acceptance qualifies the feature.

Unchanged: app-owned IDs, exact-quote confirmation, fail-closed passes,
invalidation on every utterance, labeled demo mode, and the rule that offline tests
prove orchestration, not model quality.

## 11. Decisions for the user

1. **North Star capture:** extract the six fields from the conversation and confirm
   them in playback (recommended; adds no turn), or ask them as an opening question.
2. **Canary threshold:** the proposal is 100% of cost-2/3 canaries and 80% overall.
   Stricter thresholds block more sessions on unreliable reviewers.
3. **Scenario approval:** replace the prose playback approval (recommended) or add
   scenarios beside it.
