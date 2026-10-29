# Editable Markdown vault implementation

Goal: turn Intent's text-only plan graph into a persistent editable Markdown vault
with an interactive graph centered on the main plan note.

Architecture: keep vault content in separate SQLite rows, versioned with optimistic
concurrency. Project validated plans into linked Markdown notes without modifying
canonical plans or the intent ledger. Derive the browser graph from parsed links.

Tech stack: existing FastAPI/Pydantic/SQLite and Next.js/React/TypeScript; d3-force
for graph layout, react-markdown for safe rendering, Markdown AST parsing, and
fflate for packaging selected Markdown files for the bounded import endpoint.

```text
GET vault ──> saved notes ──> file list / editor / preview
                  │                   │
                  └── parse links ──> graph + backlinks
                                      │ drag / pan / zoom
Editor changes ──> POST expected revision ──> atomic SQLite save
                         │ mismatch/error
                         └── preserve draft + show recovery
Validated plan ──> explicit seed ──> linked notes + source identity
ZIP / Markdown ──> bounded validation ──> explicit import replacement
Saved vault ──> safe portable ZIP
```

## Files and checkpoints

- `backend/app/vault/`: strict contracts, persistence, safe ZIP handling, deterministic
  plan-to-note projection, and session-scoped routes. `backend/app/main.py` registers
  these routes. `backend/tests/test_vault.py` covers persistence and boundaries.
- `frontend/lib/vault.ts` and `vault.test.ts`: note paths, AST/wiki links, graph
  projection, safe rename and viewport transforms. `frontend/lib/use-vault.ts`
  owns draft/saved state and serialized autosave with conflict recovery.
- `frontend/components/vault-graph.tsx`: force simulation, drag, pan, zoom, accessible
  node selection and graph controls. `vault-workspace.tsx` owns notes and editor UI.
  A scoped CSS file styles these components; `plan-panel.tsx` adds the view.
- Existing dependency manifests and README record installed dependencies and usage.

## Execution

- [x] Install dependencies, read the installed Next.js client-component guide, and
  run existing frontend tests. Expected: baseline tests pass before behavior edits.
- [x] Write failing backend vault tests; run `uv run pytest backend/tests/test_vault.py -q`.
  Expected initially: missing vault module or endpoints. Add contracts, atomic store,
  bounded archive import/export, plan seed and routes. Rerun until green. Run the
  complete backend suite and Ruff before the backend checkpoint commit.
- [x] Write failing frontend link/rename/viewport tests; run `npm test`. Expected
  initially: missing vault helpers. Implement AST parsing, wiki links, path resolution,
  graph projection, safe rename and coordinate math. Verify tests/typecheck before
  committing the coherent link-model checkpoint.
- [x] Implement serialized autosave and editor/file actions against the tested API.
  Add force graph, pointer/keyboard controls, filters and display controls. Preserve
  drafts across tab switches; show conflict and stale-source states. Verify frontend
  tests, typecheck and production build, plus scripted demo smoke.
- [x] Start an owned loopback demo server on separate ports, inspect desktop and
  narrow layouts, and exercise create/edit/link/rename/delete, missing notes, drag,
  pan/zoom, save/reload, import/export, plan seeding and conflict recovery. Fix observed
  issues, repeat affected checks, and commit the UI checkpoint.
- [x] Review the diff for correctness, data-loss/security boundaries and cleanup.
  Update README with actual behavior and verification results. Commit documentation
  and report checkpoint hashes and any limitations. No push, PR or release.

## Verification record — 2026-10-29

Final backend verification: 224 passed, 1 skipped (Windows symbolic-link permission),
with the existing Starlette/httpx deprecation warning. Ruff passed. Frontend:
22 tests passed, TypeScript passed, Prettier passed, and the production build passed.
All 16 scripted demo evaluations completed with zero model calls. These fixtures
establish pipeline behavior, not model quality.

An earlier full run had seven subprocess timing failures; an isolated retry had
four startup timeouts in the existing 0.5-second transport tests. A subsequent full
run with the owned dev server stopped passed all tests without changing those
tests or their timeouts. Preserve this timing sensitivity as a verification caveat.

Browser checks covered Markdown editing and preview, note creation and renaming,
automatic link updates, missing-node creation, backlinks, deletion confirmation,
node dragging, canvas panning, zoom, fit, graph controls, autosave and view/reload
restoration, ZIP export/import through the picker and explicit replacement dialog,
and a real concurrent-save conflict that retained the local draft. A 390px viewport
stacked the inspector beneath the graph without horizontal document overflow.
The production preview restored a 13-note/36-link synthetic plan and reported no
browser console errors. Owned preview services remain on loopback ports 3001/8001,
using `.data/vault-browser.sqlite3`; the separate checkout on 3000/8000 was untouched.
Screenshots and diagnostic reports remain ignored under `.data/vault-check/`.

Correctness/security review checked source-plan immutability, revision comparisons,
draft preservation, archive path/size/symlink boundaries, raw HTML and external-link
handling. Production dependency audit reported zero advisories. The existing Vitest
3 development dependency tree still reports three advisories (one moderate, two
critical); no test-framework major upgrade is included in this feature.

Runtime QA found and fixed a Strict Mode modal cleanup issue and an autosave loop
caused by JSON object-key order. A regression test now proves equal note values
do not trigger another save when the server serializes keys in a different order.
Graph expansion is bounded to 750 nodes and 5,000 edges with an explicit notice;
all Markdown survives in the explorer and exports. Exported plan-note links also
resolve when the root note has been moved into a folder.

Checkpoints on `codex/markdown-vault`: `b6973ac` design/plan, `4c8c2dd` persistence and
archive API, `584ed7b` link model and serialized saves, `fb864b4` snapshot/loopback
hardening, and `f5ea82c` interactive graph and editor. Documentation follows in a
separate checkpoint. No push, PR, merge, deployment or provider request was made.
