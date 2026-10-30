"use client";

import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { strToU8, zipSync } from "fflate";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Check,
  ChevronRight,
  CircleDashed,
  FilePlus2,
  FileText,
  FolderOpen,
  GitBranch,
  Image as ImageIcon,
  LoaderCircle,
  Maximize2,
  Minimize2,
  Network,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { api } from "@/lib/stream";
import { useVault } from "@/lib/use-vault";
import {
  graphFromNotes,
  noteTitle,
  previewMarkdown,
  renameNote,
  resolveLink,
  validateNotePath,
  type GraphNode,
  type VaultDocument,
  type VaultNote,
} from "@/lib/vault";
import type { Session } from "@/lib/types";
import { VaultGraph } from "./vault-graph";
import "./vault.css";

function NotePathDialog({
  initial,
  title,
  onSubmit,
  onClose,
}: {
  initial: string;
  title: string;
  onSubmit: (path: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [path, setPath] = useState(initial);
  const [error, setError] = useState("");
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    element?.querySelector("input")?.focus();
    return () => {
      element?.close();
    };
  }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const value = /\.md$/i.test(path.trim())
        ? path.trim()
        : path.trim() + ".md";
      validateNotePath(value);
      onSubmit(value);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invalid note path.");
    }
  }
  return (
    <dialog
      ref={dialog}
      className="vault-dialog"
      onCancel={onClose}
      aria-labelledby="vault-dialog-title"
    >
      <form onSubmit={submit}>
        <div className="vault-dialog-heading">
          <h3 id="vault-dialog-title">{title}</h3>
          <button
            type="button"
            className="vault-icon-button"
            onClick={onClose}
            aria-label="Close note dialog"
          >
            <X size={18} />
          </button>
        </div>
        <label htmlFor="vault-note-path">Note path</label>
        <input
          autoFocus
          id="vault-note-path"
          value={path}
          maxLength={240}
          onChange={(e) => setPath(e.target.value)}
          placeholder="ideas/My note.md"
          autoComplete="off"
        />
        <p>
          Use folders to organize notes. Internal links update when you rename.
        </p>
        {error && (
          <p role="alert" className="vault-form-error">
            {error}
          </p>
        )}
        <div className="vault-dialog-actions">
          <button type="button" className="vault-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="vault-button is-primary">
            {title === "Rename note" ? "Rename" : "Create note"}
            <ChevronRight size={14} />
          </button>
        </div>
      </form>
    </dialog>
  );
}

function downloadDraft(notes: VaultNote[]) {
  const root = notes.find((n) => n.id === "plan")!;
  const files = Object.fromEntries(notes.map((n) => [n.path, strToU8(n.body)]));
  files["intent-vault.json"] = strToU8(
    JSON.stringify({
      format: "intent-markdown-vault-v1",
      root_path: root.path,
      notice: "Unsaved editable draft; not an approved execution bundle.",
      notes: notes.map((n) => ({ path: n.path, kind: n.kind })),
    }),
  );
  const bytes = zipSync(files);
  const url = URL.createObjectURL(
    new Blob([new Uint8Array(bytes)], { type: "application/zip" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "intent-vault-draft.zip";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

type Confirmation = { title: string; message: string; action: () => void };
function ConfirmVaultAction({
  confirmation,
  close,
}: {
  confirmation: Confirmation;
  close: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="vault-dialog"
      onCancel={close}
      aria-label={confirmation.title}
    >
      <h3>{confirmation.title}</h3>
      <p>{confirmation.message}</p>
      <div className="vault-dialog-actions">
        <button className="vault-button" onClick={close}>
          Cancel
        </button>
        <button
          className="vault-button is-primary"
          onClick={() => {
            close();
            confirmation.action();
          }}
        >
          Confirm
        </button>
      </div>
    </dialog>
  );
}

export function VaultWorkspace({
  session,
  canSeed,
  readOnly,
}: {
  session: Session;
  canSeed: boolean;
  readOnly: boolean;
}) {
  const { sync, state, dirty, base, loadError, reloadSaved, retryLoad } =
    useVault(session.id);
  const [selected, setSelected] = useState("plan");
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [showFiles, setShowFiles] = useState(true);
  const [operation, setOperation] = useState(false);
  const [actionError, setActionError] = useState("");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [dialog, setDialog] = useState<{
    title: string;
    path: string;
    rename?: string;
  } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const notes = state?.notes ?? [];
  const deferredNotes = useDeferredValue(notes);
  const graph = useMemo(() => graphFromNotes(deferredNotes), [deferredNotes]);
  const selectedNote = notes.find((n) => n.id === selected);
  const selectedNode = graph.nodes.find((n) => n.id === selected);
  const backlinks = graph.edges
    .filter((e) => e.target === selected)
    .map((e) => notes.find((n) => n.id === e.source))
    .filter((n): n is VaultNote => !!n);
  const locked = readOnly || operation;
  const canTransfer = !!state && !dirty && !state.saving && !operation;
  const stale =
    !!state?.saved.source &&
    (state.saved.source.requirements_revision !== session.revision ||
      session.planning.status === "stale" ||
      (!!session.planning.active &&
        state.saved.source.revision !== session.planning.active.revision));

  useEffect(() => {
    if (!expanded) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !(event.target as Element).closest("dialog")
      )
        setExpanded(false);
    };
    window.addEventListener("keydown", escape);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", escape);
    };
  }, [expanded]);

  useEffect(() => {
    if (
      selected.startsWith("missing:") &&
      notes.some((n) => `missing:${n.path.toLowerCase()}` === selected)
    )
      setSelected(
        notes.find((n) => `missing:${n.path.toLowerCase()}` === selected)!.id,
      );
  }, [selected, notes]);

  function open(node: GraphNode) {
    setSelected(node.id);
    setActionError("");
  }
  function create(path: string) {
    if (!sync || locked) return;
    if (notes.length >= 500)
      throw new Error("A vault supports up to 500 notes.");
    if (notes.some((n) => n.path.toLowerCase() === path.toLowerCase()))
      throw new Error("A note already uses that path.");
    const note: VaultNote = {
      id: crypto.randomUUID(),
      path,
      kind: "note",
      body: `# ${path.split("/").at(-1)!.replace(/\.md$/i, "")}\n\n`,
    };
    sync.update([...notes, note]);
    setSelected(note.id);
    setMode("edit");
    setDialog(null);
  }
  function submitPath(path: string) {
    if (!dialog || !sync) return;
    if (dialog.rename) {
      sync.update(renameNote(notes, dialog.rename, path));
      setDialog(null);
    } else create(path);
  }
  async function seed() {
    if (!sync || !canTransfer || locked) return;
    setOperation(true);
    await sync.replace((expected_revision) =>
      api<VaultDocument>(base + "/seed", { expected_revision }),
    );
    setOperation(false);
  }
  async function importFiles(
    files: FileList | File[] | null,
    confirmed = false,
  ) {
    if (!files?.length || !sync || !canTransfer || locked) return;
    const selection = Array.from(files);
    if (state!.saved.revision > 0 && !confirmed) {
      setConfirmation({
        title: "Replace this vault?",
        message: `Replace this vault's ${notes.length} notes with the imported files? Export a backup first if you want to keep them.`,
        action: () => void importFiles(selection, true),
      });
      return;
    }
    setActionError("");
    setOperation(true);
    try {
      let bytes: Uint8Array;
      if (selection.length === 1 && /\.zip$/i.test(selection[0].name)) {
        if (selection[0].size > 3_000_000)
          throw new Error("ZIP exceeds the 3 MB upload limit.");
        bytes = new Uint8Array(await selection[0].arrayBuffer());
      } else {
        if (
          selection.length > 500 ||
          selection.some((f) => !/\.md$/i.test(f.name) || f.size > 100_000) ||
          selection.reduce((sum, f) => sum + f.size, 0) > 2_000_000
        )
          throw new Error(
            "Choose up to 500 Markdown files: 100 KB per note, 2 MB total.",
          );
        const entries: Record<string, Uint8Array> = {};
        for (const file of selection) {
          const path = validateNotePath(file.webkitRelativePath || file.name);
          if (
            Object.keys(entries).some(
              (key) => key.toLowerCase() === path.toLowerCase(),
            )
          )
            throw new Error("Imported note paths must be unique.");
          entries[path] = new Uint8Array(await file.arrayBuffer());
        }
        bytes = zipSync(entries);
      }
      await sync.replace(async (revision) => {
        const response = await fetch(
          `/api${base}/import?expected_revision=${revision}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/zip" },
            body: new Uint8Array(bytes),
          },
        );
        if (!response.ok) {
          const error = await response.json();
          throw new Error(
            typeof error.detail === "string"
              ? error.detail
              : "Import rejected. Existing notes were preserved.",
          );
        }
        return response.json();
      });
      if (!sync.state.error) {
        setSelected("plan");
        setMode("preview");
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Import failed.");
    } finally {
      setOperation(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (!state || !sync)
    return (
      <div className="vault-loading">
        {loadError ? (
          <>
            <p role="alert">{loadError}</p>
            <button className="secondary-button" onClick={retryLoad}>
              Retry loading vault
            </button>
          </>
        ) : (
          <>
            <LoaderCircle size={20} className="spin" />
            Opening your notes…
          </>
        )}
      </div>
    );

  return (
    <section
      className={`vault-workspace ${expanded ? "is-expanded" : ""} ${showFiles ? "show-files" : ""}`}
      aria-label="Editable Markdown vault"
      onKeyDown={(event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "s") {
          event.preventDefault();
          sync.retry();
          void sync.save();
        }
      }}
    >
      <header className="vault-toolbar">
        <div className="vault-toolbar-title">
          <Network size={18} />
          <div>
            <strong>Graph & notes</strong>
            <span>Your plan, connected.</span>
          </div>
        </div>
        <div className="vault-toolbar-actions">
          <span
            className={`vault-save-status ${state.error ? "has-error" : ""}`}
            role="status"
          >
            {state.saving ? (
              <LoaderCircle size={12} className="spin" />
            ) : dirty ? (
              <CircleDashed size={12} />
            ) : (
              <Check size={13} />
            )}
            {state.saving
              ? "Saving…"
              : state.error
                ? "Needs attention"
                : dirty
                  ? "Unsaved"
                  : "Saved locally"}
          </span>
          <button
            className="vault-icon-button"
            aria-label="Toggle file list"
            aria-pressed={showFiles}
            onClick={() => setShowFiles(!showFiles)}
          >
            <FolderOpen size={16} />
          </button>
          <button
            className="vault-icon-button"
            aria-label={
              expanded ? "Exit expanded graph" : "Expand graph workspace"
            }
            aria-pressed={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>
        </div>
      </header>
      <div className="vault-context">
        <span>
          {session.mode === "demo" ? "DEMO WORKSPACE" : "LOCAL WORKSPACE"}
        </span>
        <p>
          {stale
            ? "This plan snapshot is older than the current requirements or plan. Your notes are preserved."
            : state.saved.source_status === "draft"
              ? "Notes include draft plan sections. Final plan validation was pending at import."
              : "Editable notes · changes here do not approve or alter the generated plan."}
        </p>
      </div>
      {(state.error || actionError || loadError) && (
        <div className="vault-error" role="alert">
          <p>{state.error || actionError || loadError}</p>
          <div>
            {dirty && (
              <button
                className="vault-button"
                onClick={() => downloadDraft(notes)}
              >
                Download draft backup
              </button>
            )}
            <button
              className="vault-button"
              disabled={state.saving}
              onClick={() => {
                setActionError("");
                sync.retry();
                void sync.save();
              }}
            >
              Retry save
            </button>
            <button
              className="vault-button"
              disabled={state.saving}
              onClick={() => {
                if (!dirty) void reloadSaved();
                else
                  setConfirmation({
                    title: "Reload saved notes?",
                    message:
                      "Discard your unsaved draft and reload the saved vault? Download a draft backup first to keep it.",
                    action: () => void reloadSaved(),
                  });
              }}
            >
              Reload saved copy
            </button>
          </div>
        </div>
      )}
      {graph.truncated && (
        <p className="vault-graph-limit" role="status">
          The graph displays up to 750 nodes and 5,000 connections. All Markdown
          content remains in your notes and export.
        </p>
      )}
      <div className="vault-grid">
        <nav className="vault-files" aria-label="Vault notes">
          <div className="vault-files-heading">
            <span>Notes</span>
            <button
              className="vault-button vault-new-note"
              aria-label="New note"
              disabled={locked}
              onClick={() => setDialog({ title: "New note", path: "" })}
            >
              <FilePlus2 size={16} />
              <span>New note</span>
            </button>
          </div>
          <label className="vault-search">
            <Search size={13} />
            <input
              aria-label="Search notes"
              placeholder="Find a note…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                className="vault-icon-button"
                aria-label="Clear search"
                onClick={() => setQuery("")}
              >
                <X size={12} />
              </button>
            )}
          </label>
          <div className="vault-note-list">
            {[...notes]
              .sort((a, b) =>
                a.id === "plan"
                  ? -1
                  : b.id === "plan"
                    ? 1
                    : a.path.localeCompare(b.path),
              )
              .filter(
                (n) =>
                  !query ||
                  `${n.path} ${noteTitle(n)}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
              )
              .map((note) => (
                <button
                  key={note.id}
                  className={`vault-file ${selected === note.id ? "is-active" : ""}`}
                  onClick={() => setSelected(note.id)}
                  aria-current={selected === note.id ? "page" : undefined}
                  title={note.path}
                >
                  {note.id === "plan" ? (
                    <Network size={15} />
                  ) : (
                    <FileText size={14} />
                  )}
                  <span>
                    {note.path.includes("/") && (
                      <small>
                        {note.path.slice(0, note.path.lastIndexOf("/"))}/
                      </small>
                    )}
                    {note.path.split("/").at(-1)!.replace(/\.md$/i, "")}
                  </span>
                  {note.id === "plan" && <i>main</i>}
                </button>
              ))}
          </div>
          <div className="vault-file-actions">
            <button
              className="vault-button"
              disabled={
                locked || !canTransfer || !canSeed || !!state.saved.source
              }
              onClick={() => void seed()}
              title={
                state.saved.source
                  ? "A plan snapshot is already in this vault."
                  : "Add linked notes from the current phase plan"
              }
            >
              <GitBranch size={14} />
              Add phase plan
            </button>
            <button
              className="vault-button"
              disabled={locked || !canTransfer}
              onClick={() => fileInput.current?.click()}
            >
              <ArrowUpFromLine size={14} />
              Import Markdown / ZIP
            </button>
            {canTransfer ? (
              <a className="vault-button" href={`/api${base}/export`} download>
                <ArrowDownToLine size={14} />
                Export vault
              </a>
            ) : (
              <button
                className="vault-button"
                onClick={() => downloadDraft(notes)}
              >
                <ArrowDownToLine size={14} />
                Export draft
              </button>
            )}
            <input
              type="file"
              ref={fileInput}
              accept=".md,.zip"
              multiple
              hidden
              aria-label="Import Markdown files or ZIP"
              onChange={(e) => void importFiles(e.target.files)}
            />
            <p>
              {notes.length} {notes.length === 1 ? "note" : "notes"} · Markdown
            </p>
          </div>
        </nav>
        <VaultGraph
          graph={graph}
          selected={selected}
          query={query}
          onSelect={open}
          storageKey={`intent-vault-layout:${session.id}`}
        />
        <aside className="vault-inspector" aria-label="Selected note">
          {selectedNote ? (
            <>
              <div className="vault-note-header">
                <div>
                  <span className="vault-kind">
                    {selectedNote.kind === "plan"
                      ? "MAIN PLAN"
                      : selectedNote.kind.toUpperCase()}
                  </span>
                  <h4 title={selectedNote.path}>
                    {selectedNote.path.split("/").at(-1)}
                  </h4>
                </div>
                <div>
                  <button
                    className="vault-icon-button"
                    aria-label="Rename note"
                    disabled={locked}
                    onClick={() =>
                      setDialog({
                        title: "Rename note",
                        path: selectedNote.path,
                        rename: selectedNote.id,
                      })
                    }
                  >
                    <Pencil size={14} />
                  </button>
                  {selectedNote.id !== "plan" && (
                    <button
                      className="vault-icon-button"
                      aria-label="Delete note"
                      disabled={locked}
                      onClick={() => {
                        setConfirmation({
                          title: "Delete this note?",
                          message: `Delete ${selectedNote.path}? Links to this note will remain as missing links.`,
                          action: () => {
                            sync.update(
                              notes.filter((n) => n.id !== selectedNote.id),
                            );
                            setSelected("plan");
                          },
                        });
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
              <div
                className="vault-editor-tabs"
                role="group"
                aria-label="Note view"
              >
                <button
                  aria-pressed={mode === "preview"}
                  onClick={() => setMode("preview")}
                >
                  Read
                </button>
                <button
                  aria-pressed={mode === "edit"}
                  onClick={() => setMode("edit")}
                >
                  Edit Markdown
                </button>
                <span>.md</span>
              </div>
              {mode === "edit" ? (
                <textarea
                  className="vault-editor"
                  aria-label="Markdown content"
                  value={selectedNote.body}
                  spellCheck={false}
                  disabled={locked}
                  maxLength={100_000}
                  onChange={(e) =>
                    sync.update(
                      notes.map((n) =>
                        n.id === selectedNote.id
                          ? { ...n, body: e.target.value }
                          : n,
                      ),
                    )
                  }
                />
              ) : (
                <div className="vault-markdown" ref={preview}>
                  <Markdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ href, children }) => {
                        const target = resolveLink(
                          notes,
                          selectedNote.path,
                          href || "",
                        );
                        return target ? (
                          <a
                            href={href}
                            className={
                              !target.note ? "is-unresolved" : undefined
                            }
                            onClick={(event) => {
                              event.preventDefault();
                              setSelected(
                                target.note?.id ??
                                  `missing:${target.path.toLowerCase()}`,
                              );
                              setMode("preview");
                            }}
                          >
                            {children}
                            {!target.note && <sup>↗</sup>}
                          </a>
                        ) : (
                          <a
                            href={href}
                            target={
                              href?.startsWith("#") ? undefined : "_blank"
                            }
                            rel="noopener noreferrer"
                          >
                            {children}
                          </a>
                        );
                      },
                      img: ({ alt }) => (
                        <span className="vault-image-placeholder">
                          <ImageIcon size={14} />
                          {alt || "Image"} · attachment
                        </span>
                      ),
                    }}
                  >
                    {previewMarkdown(selectedNote, notes)}
                  </Markdown>
                  {!selectedNote.body.trim() && (
                    <p className="vault-empty-note">
                      This note is empty. Switch to Edit Markdown to start
                      writing.
                    </p>
                  )}
                </div>
              )}
              <div className="vault-backlinks">
                <h5>
                  BACKLINKS <span>{backlinks.length}</span>
                </h5>
                {backlinks.length ? (
                  backlinks.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        setSelected(n.id);
                        setMode("preview");
                      }}
                    >
                      <FileText size={12} />
                      {noteTitle(n)}
                      <ChevronRight size={12} />
                    </button>
                  ))
                ) : (
                  <p>No notes link here yet.</p>
                )}
              </div>
              <footer className="vault-note-footer">
                <span>
                  {new TextEncoder()
                    .encode(selectedNote.body)
                    .length.toLocaleString()}{" "}
                  bytes
                </span>
                <span>[[Link]] to connect</span>
              </footer>
            </>
          ) : (
            <div className="vault-missing">
              <CircleDashed size={28} />
              <h4>{selectedNode?.path || "Missing note"}</h4>
              <p>A link points here, but the note doesn’t exist yet.</p>
              <button
                className="vault-button is-primary"
                disabled={locked || !selectedNode}
                onClick={() =>
                  setDialog({
                    title: "Create linked note",
                    path: selectedNode!.path,
                  })
                }
              >
                <Plus size={15} />
                Create this note
              </button>
            </div>
          )}
        </aside>
      </div>
      <footer className="vault-statusbar">
        <span>
          <span className="vault-live-dot" />
          LOCAL MARKDOWN VAULT
        </span>
        <span>
          Click to read · drag to arrange · {graph.edges.length} connections
        </span>
      </footer>
      {dialog && (
        <NotePathDialog
          initial={dialog.path}
          title={dialog.title}
          onSubmit={submitPath}
          onClose={() => setDialog(null)}
        />
      )}
      {confirmation && (
        <ConfirmVaultAction
          confirmation={confirmation}
          close={() => {
            setConfirmation(null);
            if (fileInput.current) fileInput.current.value = "";
          }}
        />
      )}
    </section>
  );
}
