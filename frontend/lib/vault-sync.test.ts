import { describe, expect, it } from "vitest";
import { VaultSync } from "./vault-sync";
import type { VaultDocument } from "./vault";

const document: VaultDocument = {
  revision: 1,
  notes: [{ id: "plan", kind: "plan", path: "Plan.md", body: "# Plan" }],
  source: null,
  source_status: null,
  demo: true,
};

describe("vault save serialization", () => {
  it("does not resave identical notes when the server changes JSON field order", async () => {
    const sync = new VaultSync(document, async (revision, notes) => ({
      ...document,
      revision: revision + 1,
      notes: notes.map((n) => ({
        body: n.body,
        kind: n.kind,
        path: n.path,
        id: n.id,
      })),
    }));
    sync.update([{ ...document.notes[0], body: "Updated" }]);
    await sync.save();
    expect(sync.dirty).toBe(false);
  });
  it("retains edits made during a save and uses the returned revision for the next save", async () => {
    let complete!: (value: VaultDocument) => void;
    const calls: number[] = [];
    const sync = new VaultSync(document, async (revision, notes) => {
      calls.push(revision);
      if (calls.length === 1)
        return new Promise((resolve) => {
          complete = resolve;
        });
      return { ...document, revision: revision + 1, notes };
    });
    sync.update([{ ...document.notes[0], body: "first" }]);
    const saving = sync.save();
    sync.update([{ ...document.notes[0], body: "newer" }]);
    await sync.save();
    expect(calls).toEqual([1]);
    complete({
      ...document,
      revision: 2,
      notes: [{ ...document.notes[0], body: "first" }],
    });
    await saving;
    expect(sync.state.notes[0].body).toBe("newer");
    expect(sync.dirty).toBe(true);
    await sync.save();
    expect(calls).toEqual([1, 2]);
    expect(sync.dirty).toBe(false);
  });
  it("keeps the unsaved buffer on conflicts and stops automatic retries", async () => {
    let calls = 0;
    const sync = new VaultSync(document, async () => {
      calls++;
      throw new Error("Changed in another window");
    });
    sync.update([{ ...document.notes[0], body: "mine" }]);
    await sync.save();
    await sync.save();
    expect(calls).toBe(1);
    expect(sync.state.error).toContain("another window");
    expect(sync.state.notes[0].body).toBe("mine");
    expect(sync.dirty).toBe(true);
    sync.retry();
    await sync.save();
    expect(calls).toBe(2);
  });
});
