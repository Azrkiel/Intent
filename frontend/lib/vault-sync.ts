import type { VaultDocument, VaultNote } from "./vault";

export interface VaultState {
  saved: VaultDocument;
  notes: VaultNote[];
  saving: boolean;
  error: string;
}
export class VaultSync {
  state: VaultState;
  onChange = (_state: VaultState) => {};
  constructor(
    document: VaultDocument,
    private persist: (
      revision: number,
      notes: VaultNote[],
    ) => Promise<VaultDocument>,
  ) {
    this.state = {
      saved: document,
      notes: document.notes,
      saving: false,
      error: "",
    };
  }
  get dirty() {
    return (
      JSON.stringify(this.state.notes) !==
      JSON.stringify(this.state.saved.notes)
    );
  }
  private emit(change: Partial<VaultState>) {
    this.state = { ...this.state, ...change };
    this.onChange(this.state);
  }
  update(notes: VaultNote[]) {
    this.emit({ notes });
  }
  retry() {
    this.emit({ error: "" });
  }
  async save() {
    if (!this.dirty || this.state.saving || this.state.error) return;
    const { notes, saved } = this.state;
    this.emit({ saving: true });
    try {
      this.emit({ saved: await this.persist(saved.revision, notes) });
    } catch (error) {
      this.emit({
        error:
          error instanceof Error
            ? error.message
            : "Save failed. Your draft is preserved.",
      });
    } finally {
      this.emit({ saving: false });
    }
  }
  async replace(action: (revision: number) => Promise<VaultDocument>) {
    if (this.dirty || this.state.saving) return;
    this.emit({ saving: true, error: "" });
    try {
      const document = await action(this.state.saved.revision);
      this.emit({ saved: document, notes: document.notes });
    } catch (error) {
      this.emit({
        error:
          error instanceof Error ? error.message : "Vault operation failed.",
      });
    } finally {
      this.emit({ saving: false });
    }
  }
  restore(document: VaultDocument) {
    if (!this.state.saving)
      this.emit({ saved: document, notes: document.notes, error: "" });
  }
}
