# Interactive graph implementation

Goal: make graph sections conversational and accept Unicode plan descriptions.
Architecture: retain the immutable plan/ledger; add source-bound discussion records
and route direction through the existing intent pipeline. The browser owns selected
node drafts and dictation lifecycle; the server owns source identity and requests.
Stack: existing FastAPI/Pydantic/SQLite and Next.js/React/SVG; no new runtime dependency.

The human approved continuation and publication with: "hey codex can you continue
where you left off? just finish the handoff and commit and PR everything".
This supersedes the earlier proposed status and no-publication scope; it does not
authorize another live planning attempt, generated execution, merging or release.

## Contract between backend and frontend

`GET /api/sessions/{id}/discussion?node_id=root` resolves a graph node on the server.
Use `node_id=intent` for the current draft-vision root, including before any plan.
Response: `{target,title,breadcrumbs,can_write,reason,messages,history,activity}`.
Activity is a revision-bound overlay of message counts and direction awaiting review.

`target` is `{kind: "plan"|"intent", requirements_revision: number,
plan_id: string|null, plan_revision: number|null, plan_hash: string|null,
node_id: string, node_hash: string}`. Requests echo the exact target returned by GET.
`breadcrumbs` are `{id,title}` entries. Historical threads are read-only.

`POST /api/sessions/{id}/discussion` accepts
`{request_id,target,mode: "question"|"direction",text}`. Question returns
`{message,session}`; direction returns the same after the ordinary intent pipeline.
A message is `{id,request_id,mode,text,status,reply,error,turn_number,created_at}`.
Status: `pending|complete|failed|uncertain`. Reply is null or
`{text,citations:string[],follow_up:string|null,proposed_direction:string|null}`.
Allowed citation addresses are server-supplied `node:<id>` / `ledger:<id>`.
An uncertain request is never replayed automatically. A reused request ID with
different payload is rejected. Direction preserves exact submitted text and stores
its target separately as turn scope. It invalidates execution/approvals before inference.

```text
Select current node -> load source-bound thread -> type / dictate / edit
  question -> reserve unique request -> bounded explanation -> validate sources
  direction -> preview -> invalidate -> exact scoped turn -> existing intent analysis
  stale / duplicate mismatch / failure / interruption -> retain evidence, no replay
```

## Tasks and ownership

- [x] Lead: write failing Unicode/control/size/preservation tests; remove ASCII
  schema/application checks, conversion helper and ASCII-only prompts/labels.
  Keep bounded repair and output-limit handling. Run focused contract/model tests.
- [x] Backend worker: own new discussion contracts/service/store/routes and tests;
  own integration in `main.py`, `domain.py`, `engine.py`, `demo.py`, `store.py`.
  Test source binding, citations, idempotency, restart, budget, history, direction
  evidence/invalidation, and mode guards before implementing each behavior.
- [x] Frontend worker: own frontend components/helpers/styles/tests. Promote graph,
  add selected-node discussion and draft root, per-node persisted drafts, explicit
  direction preview, and safe text/dictation lifecycle. Read frontend instructions
  and installed Next.js guides. Run Vitest/typecheck and report build needs.
- [x] Lead: integrate, test request/selection races, review security and simplify.
  Run `uv run pytest -q`, `uv run ruff check backend`, `npm test`,
  `npm run typecheck`, `npm run build`, and `npm run eval:demo`.
  Stop owned servers before building; browser-check an isolated labeled fixture.
- [x] Lead: update spec/README/current handoff with actual evidence and limits;
  commit coherent verified milestones. Keep keys, sessions, reports and generated
  artifacts ignored. Push the named branch and open/attach a PR against main,
  preserving the existing checkout and honest failed live-qualification history.

Reference: [approved design](../specs/2026-10-28-interactive-plan-graph.md).

## Verification, 2026-10-29

Full backend: 415 passed, one existing Windows symlink skip and one deprecation
warning; Ruff passed. Frontend: 31 tests, typecheck and production build passed.
Demo pipeline: 16/16, zero provider calls. Independent review findings on uncertain
requests and worker-limit source hashes were fixed and verified. Security inspection
covered source/mode guards, SQL parameters, text-only rendering and paid-call gates;
cleanup retained the existing adapter and intent flow without new runtime dependencies.
Browser checks covered desktop/mobile, drafts/reload, scoped answers, exact direction,
stale gating, current-vision entry, Unicode and keyboard selection. QA exposed and
fixed cached planning state after direction. Speech lifecycle uses simulated tests;
real microphone and live explanation quality remain unverified. The retained live
session's raw SQLite bytes and all attempt/usage counts match the pre-change audit.

Published [PR #3](https://github.com/Azrkiel/Intent/pull/3) against `main` and attached
it to the chat. Checkpoint details and remaining limits are in the
latest handoff (session handoff 2026-10-29-0035, not retained). No merge or release occurred.
