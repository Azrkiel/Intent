import type { Session } from "./types";
import type { PlanIdentity } from "./planning";

export interface DiscussionTarget {
  kind: "plan" | "intent";
  requirements_revision: number;
  plan_id: string | null;
  plan_revision: number | null;
  plan_hash: string | null;
  node_id: string;
  node_hash: string;
}
export interface DiscussionReply {
  text: string;
  citations: string[];
  follow_up: string | null;
  proposed_direction: string | null;
}
export interface DiscussionMessage {
  id: string;
  request_id: string;
  mode: "question" | "direction";
  text: string;
  status: "pending" | "complete" | "failed" | "uncertain";
  reply: DiscussionReply | null;
  error: string | null;
  turn_number: number | null;
  created_at: number;
}
export interface DiscussionView {
  target: DiscussionTarget;
  title: string;
  breadcrumbs: { id: string; title: string }[];
  can_write: boolean;
  reason: string | null;
  messages: DiscussionMessage[];
  history: {
    target: DiscussionTarget;
    title: string;
    messages: DiscussionMessage[];
  }[];
  activity?: DiscussionActivity;
}
export type DiscussionActivity = Record<
  string,
  { messages: number; pending_direction: boolean }
>;

export function matchesDiscussionSource(
  target: DiscussionTarget,
  source?: PlanIdentity,
): boolean {
  return source
    ? target.kind === "plan" &&
        target.requirements_revision === source.requirements_revision &&
        target.plan_id === source.plan_id &&
        target.plan_revision === source.revision &&
        target.plan_hash === source.content_hash
    : target.kind === "intent";
}
export interface DiscussionRequest {
  request_id: string;
  target: DiscussionTarget;
  mode: "question" | "direction";
  text: string;
}
export interface DiscussionResult {
  message: DiscussionMessage;
  session: Session;
}
export interface DiscussionDraft {
  text: string;
  mode: "question" | "direction";
  pending?: DiscussionRequest;
}
export function discussionKey(
  sessionId: string,
  target: DiscussionTarget,
): string {
  return (
    "intent-discussion:v1:" +
    JSON.stringify([
      sessionId,
      target.kind,
      target.requirements_revision,
      target.plan_id,
      target.plan_revision,
      target.plan_hash,
      target.node_id,
      target.node_hash,
    ])
  );
}
export function requestForDraft(
  draft: DiscussionDraft,
  target: DiscussionTarget,
  newId = () => crypto.randomUUID(),
): DiscussionRequest {
  if (draft.pending) {
    if (discussionKey("", draft.pending.target) !== discussionKey("", target)) {
      throw new Error(
        "This saved request belongs to a different section. Reload the saved discussion.",
      );
    }
    return draft.pending;
  }
  return { request_id: newId(), target, mode: draft.mode, text: draft.text };
}
export function settleDraft(
  draft: DiscussionDraft,
  requestId: string,
  status: DiscussionMessage["status"],
): DiscussionDraft {
  if (
    draft.pending?.request_id !== requestId ||
    status === "pending" ||
    status === "uncertain"
  )
    return draft;
  return {
    text:
      status === "complete" && draft.text === draft.pending.text
        ? ""
        : draft.text,
    mode: draft.mode,
  };
}
export function startDifferentDraft(
  draft: DiscussionDraft,
  saved: Pick<DiscussionMessage, "request_id" | "status"> | undefined,
): DiscussionDraft {
  if (
    !draft.pending ||
    saved?.request_id !== draft.pending.request_id ||
    saved.status !== "uncertain"
  ) {
    return draft;
  }
  return {
    text: draft.text === draft.pending.text ? "" : draft.text,
    mode: "question",
  };
}
export function readDiscussionDraft(key: string): DiscussionDraft {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    if (
      value &&
      typeof value.text === "string" &&
      ["question", "direction"].includes(value.mode)
    )
      return value;
  } catch {
    /* Storage may be unavailable; text entry remains usable. */
  }
  return { text: "", mode: "question" };
}
export function saveDiscussionDraft(key: string, draft: DiscussionDraft) {
  try {
    localStorage.setItem(key, JSON.stringify(draft));
  } catch {
    /* Keep the current in-memory draft. */
  }
}
