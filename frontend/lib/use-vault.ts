"use client";

import { useEffect, useState } from "react";
import { api } from "./stream";
import { VaultSync, type VaultState } from "./vault-sync";
import { validateNotePath, type VaultDocument, type VaultNote } from "./vault";

export function useVault(sessionId: string) {
  const base = `/sessions/${sessionId}/vault`;
  const recoveryKey = `intent-vault-draft:${sessionId}`;
  const [sync, setSync] = useState<VaultSync | null>(null);
  const [state, setState] = useState<VaultState | null>(null);
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    let active = true;
    setLoadError("");
    api<VaultDocument>(base)
      .then((document) => {
        if (!active) return;
        const model = new VaultSync(document, (expected_revision, notes) =>
          api<VaultDocument>(base, { expected_revision, notes }),
        );
        try {
          const raw = sessionStorage.getItem(recoveryKey);
          if (raw) {
            const recovered = JSON.parse(raw);
            const notes: VaultNote[] = recovered.notes;
            if (
              Array.isArray(notes) &&
              notes.length <= 500 &&
              notes.some((n) => n.id === "plan") &&
              notes.every(
                (n) =>
                  typeof n.id === "string" &&
                  typeof n.body === "string" &&
                  typeof n.path === "string" &&
                  [
                    "plan",
                    "phase",
                    "package",
                    "task",
                    "spec",
                    "screen",
                    "note",
                  ].includes(n.kind),
              )
            ) {
              notes.forEach((n) => validateNotePath(n.path));
              model.update(notes);
              if (recovered.revision !== document.revision && model.dirty)
                model.state.error =
                  "Recovered draft differs from a newer saved vault. Download your draft before reloading the saved copy.";
            }
          }
        } catch {
          /* A malformed or unavailable browser recovery entry cannot block the saved vault. */
        }
        model.onChange = (next) => {
          if (active) setState(next);
        };
        setSync(model);
        setState(model.state);
      })
      .catch((error) => {
        if (active) setLoadError(String(error));
      });
    return () => {
      active = false;
    };
  }, [base, recoveryKey, reloadKey]);

  const dirty = !!sync && sync.dirty;
  useEffect(() => {
    if (!sync || !state) return;
    try {
      if (sync.dirty)
        sessionStorage.setItem(
          recoveryKey,
          JSON.stringify({
            revision: state.saved.revision,
            notes: state.notes,
          }),
        );
      else sessionStorage.removeItem(recoveryKey);
    } catch {
      /* Autosave still works when browser storage is unavailable. */
    }
    if (!sync.dirty || state.saving || state.error) return;
    const timer = setTimeout(() => void sync.save(), 650);
    return () => clearTimeout(timer);
  }, [sync, state, recoveryKey]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  async function reloadSaved() {
    if (!sync || sync.state.saving) return;
    try {
      const document = await api<VaultDocument>(base);
      sessionStorage.removeItem(recoveryKey);
      sync.restore(document);
    } catch (error) {
      setLoadError(String(error));
    }
  }
  return {
    sync,
    state,
    dirty,
    base,
    loadError,
    reloadSaved,
    retryLoad: () => setReloadKey((key) => key + 1),
  };
}
