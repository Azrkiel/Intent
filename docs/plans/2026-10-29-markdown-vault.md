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

- [ ] Install dependencies, read the installed Next.js client-component guide, and
  run existing frontend tests. Expected: baseline tests pass before behavior edits.
- [ ] Write failing backend vault tests; run `uv run pytest backend/tests/test_vault.py -q`.
  Expected initially: missing vault module or endpoints. Add contracts, atomic store,
  bounded archive import/export, plan seed and routes. Rerun until green. Run the
  complete backend suite and Ruff before the backend checkpoint commit.
- [ ] Write failing frontend link/rename/viewport tests; run `npm test`. Expected
  initially: missing vault helpers. Implement AST parsing, wiki links, path resolution,
  graph projection, safe rename and coordinate math. Verify tests/typecheck before
  committing the coherent link-model checkpoint.
- [ ] Implement serialized autosave and editor/file actions against the tested API.
  Add force graph, pointer/keyboard controls, filters and display controls. Preserve
  drafts across tab switches; show conflict and stale-source states. Verify frontend
  tests, typecheck and production build, plus scripted demo smoke.
- [ ] Start an owned loopback demo server on separate ports, inspect desktop and
  narrow layouts, and exercise create/edit/link/rename/delete, missing notes, drag,
  pan/zoom, save/reload, import/export, plan seeding and conflict recovery. Fix observed
  issues, repeat affected checks, and commit the UI checkpoint.
- [ ] Review the diff for correctness, data-loss/security boundaries and cleanup.
  Update README with actual behavior and verification results. Commit documentation
  and report checkpoint hashes and any limitations. No push, PR or release.
