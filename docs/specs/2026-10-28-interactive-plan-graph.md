# Interactive project graph and section conversations

Date: 2026-10-28 (America/New_York).
Status: proposed for human design approval; no implementation or live calls yet.
Worktree: `C:/Users/jiang/.codex/worktrees/phase-four/intent`.
Baseline: `6bf9461`, branch `codex/phase-five-live-qualification`.

## Goal and source

Make the project graph the main planning workspace, where a person can select a
section, ask about it, and type or dictate further direction for that section.
Remove ASCII-only presentation as a condition of accepting a plan.

The human requested: "we can remove ASCII", "let's make the graph feature more
prominant", "can you include a spot where people can question/dictate the plan
and further explain their vision?", and "make the graph interactable is what I mean".
These are source quotes for this feature spec, not new ledger entries or changes
to the retained counter qualification session.

## Approaches considered

1. **Recommended: graph workspace with node conversations.** Keep the validated
   graph and immutable plan contracts, add section-specific questions and direction,
   and use the existing requirements/review flow for changes. This supplies useful
   interaction while preserving source evidence, history and execution gates.
2. **Notes attached to nodes.** Less work, but static notes do not answer questions
   or incorporate the user's vision into requirements. Insufficient on its own.
3. **Direct visual editor with model-written graph patches.** Attractive for later
   work, but introduces conflict resolution and identity/dependency changes. It
   must not let a model overwrite the ledger or mutate an approved plan in place.
   It is outside this first version.

## Workspace and interaction

- Rename the primary planning navigation to **Project graph** and give its canvas
  the main content area. Keep the root centered on entry, readable labels, search,
  collapse, pan/zoom, fit, and the accessible outline. The other text views remain
  secondary views of the same revision.
- Show a selected section panel beside the graph on desktop and below it on narrow
  screens. Its header has the section title and ancestor breadcrumb. It has
  **Discuss** and **Details** tabs; **Discuss** is the primary interaction. Exact
  hashes and raw JSON move into a secondary details disclosure.
- Use the same interaction for the project root, phase, subproject, task and screen.
  The selected node and ancestry remain visible while the person composes a message.
- The composer has explicit **Ask about this** and **Add direction** modes, a text
  field, microphone control, editable transcript, and send control. Example prompts
  include "Why is this part needed?", "What happens if it fails?", and
  "Here is how I want this part to work...".
- Show a conversation history for the selected node with human messages, grounded
  answers, and submitted direction. Node badges identify discussion activity and
  direction awaiting a new plan revision; they never mean implementation succeeded.
- Before a plan exists, show an explicitly labeled **Draft vision** root composed
  from current intent. It supports adding direction. There are no invented phases,
  work packages, plan approvals or fake plan IDs. Explain that planning will add
  the detailed branches. A missing accepted outline no longer makes the workspace
  an inert empty panel.

## Questions and direction have distinct effects

### Ask about this

This is a read-only explanation query, kept outside the canonical intent transcript.
The server supplies the selected node, flat ancestor context, relevant source
citations and direct connection summaries. It does not send all sibling task bodies
or treat quoted product text as tool instructions.

The model returns a validated explanation, references to supplied node/source
addresses, and optionally a clarifying question. Unknown citations are rejected.
Missing or pending information is described as missing; the answer must not invent
an implementation. A proposed alternative is labeled as a proposal.

An explanation cannot edit requirements, change a plan hash, approve anything,
dispatch an agent, or claim tests ran. If a query requests a change, the UI can
offer **Use this as direction**, which fills the direction draft and requires the
person to submit it. A query is not silently promoted to a requirement.

### Add direction

Typed or dictated direction remains an editable draft until submission. A short
confirmation previews the person's exact text and says that submitting changes
requirements and makes the existing plan require review. If workers are active,
the action explicitly describes stopping affected execution through the existing
invalidation path.

On **Submit direction for review**, the server validates the selected source under
the session lock, invokes execution invalidation, and creates a normal user turn
with the exact submitted text. A separate optional scope field records the source
plan/node identity; the server does not prepend generated context to `Turn.text`.

The normal turn pipeline immediately invalidates playback approval, the compiled
brief, displayed build result and plan approval, before extraction/criticism. Models
return validated ledger deltas. Confirmed requirements still need exact quotes from
the actual human turn; a model summary or explanation is not a human source.

The UI shows the submitted direction and its resulting requirements/review state.
The old immutable plan remains inspectable and stale. It is not quietly patched.
The person reviews the updated requirements and a newly generated plan revision
before execution. A local change can affect dependencies or other branches; the
UI must not promise that only the selected node will change.

```text
Select section -> Discuss
  Ask -> bounded explanation -> cited answer, plan unchanged
      -> missing context / model error / budget limit -> visible failure, no change

  Add direction -> type or dictate -> edit -> preview exact text
      cancel -> draft only
      submit -> validate current source and lock session
          stale source -> reject, preserve draft, refresh
          current source -> invalidate execution and approvals -> record exact turn
              extraction/critic failure -> preserve source, keep gates closed
              success -> requirements review -> new plan review -> optional execution
```

## Identity, storage and async behavior

- Persist discussion records separately from the immutable plan. Bind a thread to
  the session, requirements revision, full plan identity and selected node ID/body
  hash. For the draft root, use a distinct intent-revision target rather than a
  fabricated plan identity. The server resolves targets from its own projection.
- Store app-owned message IDs, mode, exact user text, validated reply, timestamps,
  request state and, for submitted direction, the resulting canonical turn number.
  Discussion text is local session content and stays out of committed artifacts.
- New plan revisions retain earlier conversations as history. Do not silently
  reattach an old `P1` conversation to a different `P1` in a new plan. Historical
  discussions are labeled and read-only; continuing in the new revision is explicit.
- Recheck revision, node and body identity before dispatch and before saving a
  reply. A stale response cannot overwrite a current panel. A node switch cannot
  deliver dictated text or a model answer into another node's draft/thread.
- Serialize model operations through the existing session lock. Use request IDs
  and durable request states so double clicks and reloads do not duplicate a billable
  request or a submitted intent turn. Interrupted/uncertain requests are shown
  honestly and are not automatically replayed on startup.
- Keep per-node drafts while switching nodes. Abort recording on switch, route
  change or unmount. Stop/abort events never submit text or apply direction.

## Voice, modes and limits

- Reuse the browser speech-recognition abstraction. Recording begins only after
  a microphone click; the transcript is visible and editable before submission.
  Unsupported browsers and denied permissions retain a working text composer.
- The UI reports recording, processing, failure and stopped states. Browser speech
  may use a vendor service; do not claim it is fully offline or record raw audio.
- Reuse the current model adapter and session dollar budget. Each explanation
  action permits one model pass and its existing single repair. Show cost/usage
  through existing accounting. Saving/selecting nodes and drafting text make no calls.
- Bound submitted human text to the existing 6000-character turn limit. Limit
  explanation text to 6000 characters, a proposed summary to 2000 characters, and
  citation addresses to 40. Context uses selected/ancestor bodies, relevant sources
  and at most the last 12 thread messages, with a 262144-byte UTF-8 ceiling. Reject
  oversized context without silently truncating it; keep the full local history.
- Questions return explanation contracts, never complete plans. They do not consume
  or replenish a full-plan attempt and cannot be used to bypass an exhausted planning
  allowance. Submitted direction follows the normal utterance and review rules;
  it does not reset consumed attempts or grants.
- Demo questions/direction remain explicitly scripted. Do not fall back from live
  failures to demo answers. This is still a local, single-user application; it does
  not add accounts, cross-device sync, mixed-agent scheduling or shared editing.

## Remove the ASCII requirement

- Accept bounded Unicode plain text in architecture descriptions, flow descriptions
  and screen-state descriptions. Preserve characters instead of transliterating
  the model's response. Keep nonempty/size constraints, valid text and escaping.
  Reject invalid Unicode and control characters such as NUL; support normal line
  breaks and tabs. Do not make a new alphabet or diagram drawing style mandatory.
- Remove the ASCII regex, ASCII-only application check, and provider-boundary glyph
  conversion introduced at `23acab5`. Keep its schema-value repair and actual
  output-limit handling. Unknown text must not be silently deleted or truncated.
- Update prompts to prefer concise architecture/flow descriptions and screen-state
  descriptions. Drawn text diagrams are optional presentation, not a special format
  a model must satisfy. The structured phases/packages/tasks remain the graph source.
- Retain existing canonical field names and older ASCII values for compatibility;
  they remain valid Unicode text. Loading an older approved plan must preserve its
  exact content hash and must not rewrite its stored data.
- Update UI/export labels such as "ASCII wireframes". Keep state coverage, citation,
  dependency, ownership, semantic verification, export and execution checks intact.

## Implementation boundaries

Expected areas, after approval:

| Area | Responsibility |
| --- | --- |
| `frontend/app/page.tsx`, `frontend/app/globals.css` | Graph navigation/prominence, workspace layout, responsive panel and states |
| `frontend/components/plan-panel.tsx`, `frontend/components/plan-graph.tsx` | Current source/selection, draft vision root, discussion/details integration |
| New graph discussion component and typed client helpers | Thread history, question/direction modes, draft ownership, request identity and errors |
| `frontend/lib/speech.ts` and a reusable dictation hook | Editable transcripts, recording lifecycle and text fallback |
| `backend/app/planning/{contracts,validation,prompts,render}.py` | Unicode descriptions, clear labels, retained plan validation |
| `backend/app/models.py`, `backend/app/planning/response.py` | Remove obsolete ASCII conversion; retain bounded repair/output-limit handling |
| New discussion contracts, service/store and routes | Source binding, read-only queries, durable requests, grounded answers and budget |
| `backend/app/{domain,engine,main,store}.py` as needed | Exact scoped user turns, existing invalidation/ledger flow, persistence compatibility |

Read `frontend/AGENTS.md` and installed Next.js client-component guides before edits;
both have been inspected during this design pass. Continue in the existing worktree.
Do not create a replacement checkout, alter the retained counter session, or publish.

## Acceptance and verification

1. Unicode arrows, box glyphs and multilingual labels pass unchanged through all
   diagram/description fields, graph data and exports; invalid/oversized text still
   fails. Previously stored ASCII plan hashes remain identical.
2. The graph is the main planning view, and a draft root remains usable without an
   accepted outline. Partial, pending, stale, blocked and demo states stay explicit.
3. Every node kind opens the correct thread; history and drafts survive navigation
   and reload without crossing sessions, nodes or revisions.
4. Questions produce grounded answers, show unknowns honestly, and cannot mutate
   intent, source plan, approvals, commands or execution state.
5. Submitted direction records exact human wording and node scope, invalidates
   approvals before inference, uses existing ledger deltas, and remains blocked
   after failed extraction/criticism. No automatic plan rewrite or agent start occurs.
6. Microphone permission denial, unsupported speech, interrupted recording, node
   switches and route changes retain text functionality and never auto-submit.
7. Double submission, concurrent turns, stale response, changed node body, budget
   exhaustion, model error and uncertain restart preserve evidence and gates.
8. Run full backend pytest/Ruff; frontend tests/typecheck/build; and labeled demo
   evaluation. Browser-check desktop/mobile, keyboard selection, questions, direction,
   stale review state and dictation via a simulated recognition interface. Real
   microphone and live model behavior remain separately qualified.

No live retry or additional planning grant is included in this design approval.
The earlier exported-viewer `file://` policy rejection remains in force.
