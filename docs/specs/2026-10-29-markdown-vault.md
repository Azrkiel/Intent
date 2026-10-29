# Editable Markdown vault and plan graph

The user selected “Make it a fully editable Markdown vault” after reviewing the
linked-plan graph design on 2026-10-29. Their original requests were “i'd like it
to be draggable, and interactive, the nodes” and “have one main node for the plan
and everything else be connected through markdown”. This is a separate UI feature,
not acceptance of the previously pending execution/review delivery phases.

## Experience

Add a Graph & notes view to Phase plan, available before a plan exists. A large,
dark graph canvas sits beside a file list and Markdown editor/preview. One larger
plan note is the root. Generate linked notes from an existing validated plan, or
start with the root and write notes manually. Create notes, rename their relative
paths, edit their bodies, delete non-root notes, and follow links or backlinks.
Rename updates resolved internal links without changing external links or code.
Deleting a note preserves inbound links as missing-note nodes that can be recreated.

Both Markdown links and Obsidian-style wikilinks create graph edges. Resolve paths
relative to their source, with case-insensitive vault lookup and unambiguous
basename lookup for wikilinks. Support aliases and heading fragments. Code, images,
external URLs, and heading-only links do not create graph edges. Missing internal
targets appear as distinct placeholders; selecting one offers note creation.

Nodes support pointer/touch dragging. The canvas supports drag-to-pan, wheel zoom,
zoom buttons, fit/reset, and keyboard navigation. Hover/focus highlights adjacent
notes. Controls include search, node-type filters, labels, arrows, node size, link
distance and repulsion, and pause/resume. Honor reduced-motion preferences. Provide
a keyboard-accessible file list and note actions as alternatives to the canvas.

## Persistence and plan ownership

Store one vault per session in the existing local SQLite database under `.data/`.
Use atomic saves with an expected revision; concurrent edits receive a conflict
instead of overwriting the saved copy. Keep the unsaved editor buffer on failures,
show saving/saved/error state, and warn before leaving with unsaved changes.
Switching plan views must preserve the editor buffer.

The vault is a user-editable workspace, separate from immutable plan revisions.
Seeding from a plan is explicit and bounded. Preserve user notes and reject path
collisions instead of overwriting them. Record source plan identity and display
demo, draft and stale context. Editing a note never confirms ledger requirements,
approves a plan, changes its hash, or starts execution. Never infer dependency
permission from an arbitrary Markdown edge.

## Portable files

Export the current saved vault as a ZIP of Markdown notes plus a small manifest.
Import Markdown files or a ZIP, with explicit confirmation before replacing existing
notes. Import restores a root note and treats all imported content as user data.
No scripts, HTML, instruction files or archive members are executed. Render Markdown
without raw HTML; external links open safely. Archive operations never extract onto
the host filesystem. Reject traversal, absolute paths, Windows special names,
case-insensitive collisions, symlinks, oversized content and oversized archives.
Limit a vault to 500 notes, 100 KB per note and 2 MB total UTF-8 content.

## Verification

Test local persistence, optimistic conflicts, safe archive round trips, malformed
and malicious imports, immutable plan preservation, link extraction/resolution,
rename behavior, missing links, and graph viewport math. Run the repository backend,
frontend and scripted demo checks. Verify the real UI in a browser using synthetic
local data; do not make provider calls or claim model-quality evidence. Stop any
owned dev server before a production build. Existing unrelated servers stay owned
by their original sessions.

Reference: [Obsidian Graph view](https://obsidian.md/help/plugins/graph) documents
nodes as notes and edges as internal links, hover highlighting, pan/zoom, display
controls and force controls. The supplied screenshots guide the dark visual layout.
