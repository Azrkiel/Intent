"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Check,
  LoaderCircle,
  MessageCircle,
  Mic,
  RefreshCw,
  Square,
} from "lucide-react";
import { api } from "@/lib/stream";
import type { Session } from "@/lib/types";
import type { PlanIdentity } from "@/lib/planning";
import { attachDictation, type DictationState } from "@/lib/dictation";
import { recognitionConstructor } from "@/lib/speech";
import {
  discussionKey,
  readDiscussionDraft,
  requestForDraft,
  saveDiscussionDraft,
  settleDraft,
  startDifferentDraft,
  matchesDiscussionSource,
  type DiscussionActivity,
  type DiscussionDraft,
  type DiscussionMessage,
  type DiscussionResult,
  type DiscussionView,
} from "@/lib/discussion";

function Message({
  message,
  useDirection,
}: {
  message: DiscussionMessage;
  useDirection?: (text: string) => void;
}) {
  return (
    <li className="discussion-message">
      <div className="discussion-message-label">
        You · {message.mode === "question" ? "Question" : "Direction"}
      </div>
      <p>{message.text}</p>
      {message.reply && (
        <div className="discussion-reply">
          <div className="discussion-message-label">
            <MessageCircle size={13} /> Section guide
          </div>
          <p>{message.reply.text}</p>
          {!!message.reply.citations.length && (
            <small>Based on: {message.reply.citations.join(" · ")}</small>
          )}
          {message.reply.follow_up && (
            <p className="discussion-followup">{message.reply.follow_up}</p>
          )}
          {message.reply.proposed_direction && useDirection && (
            <button
              className="text-button"
              onClick={() => useDirection(message.reply!.proposed_direction!)}
            >
              Use proposal as direction
            </button>
          )}
        </div>
      )}
      {message.status === "complete" && message.mode === "direction" && (
        <p className="discussion-saved">
          <Check size={13} /> Direction saved as turn {message.turn_number}.
          Review the updated requirements.
        </p>
      )}
      {message.status !== "complete" && (
        <p className="discussion-request-state" role="status">
          {message.error ||
            (message.status === "pending"
              ? "This request is still being processed."
              : message.status === "uncertain"
                ? "The outcome is uncertain. It will not be replayed automatically."
                : "This request could not complete.")}
        </p>
      )}
    </li>
  );
}

export function GraphDiscussion({
  session,
  nodeId,
  busy,
  setBusy,
  onSession,
  modeMismatch = false,
  source,
  onActivity,
}: {
  session: Session;
  nodeId: string;
  busy: boolean;
  setBusy: (value: boolean) => void;
  onSession: (value: Session) => void;
  modeMismatch?: boolean;
  source?: PlanIdentity;
  onActivity?: (activity: DiscussionActivity) => void;
}) {
  const [view, setView] = useState<DiscussionView | null>(null);
  const [draft, setDraft] = useState<DiscussionDraft>({
    text: "",
    mode: "question",
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [recording, setRecording] = useState<DictationState>("idle");
  const owner = `${session.id}:${session.revision}:${nodeId}`;
  const activeOwner = useRef(owner);
  activeOwner.current = owner;
  const alive = useRef(true);
  const storageKey = useRef("");
  const capture = useRef<ReturnType<typeof attachDictation> | null>(null);
  const sending = useRef(false);
  const loadVersion = useRef(0);
  const base = `/sessions/${session.id}/discussion`;

  function updateDraft(next: DiscussionDraft) {
    setDraft(next);
    if (storageKey.current) saveDiscussionDraft(storageKey.current, next);
  }

  async function load() {
    const version = ++loadVersion.current;
    capture.current?.dispose();
    capture.current = null;
    setRecording("idle");
    setLoading(true);
    setError("");
    try {
      const fresh = await api<DiscussionView>(
        `${base}?node_id=${encodeURIComponent(nodeId)}`,
      );
      if (
        !alive.current ||
        activeOwner.current !== owner ||
        version !== loadVersion.current
      )
        return;
      if (!matchesDiscussionSource(fresh.target, source)) {
        setView({
          ...fresh,
          can_write: false,
          reason:
            "This graph revision has changed. Reload the current plan before continuing.",
          messages: [],
          history: [],
        });
        setError(
          "This graph revision has changed. Reload the current plan before continuing.",
        );
        return;
      }
      const key = discussionKey(session.id, fresh.target);
      let saved = readDiscussionDraft(key);
      if (saved.pending) {
        const message = fresh.messages.find(
          (item) => item.request_id === saved.pending!.request_id,
        );
        if (message)
          saved = settleDraft(saved, message.request_id, message.status);
      }
      storageKey.current = key;
      saveDiscussionDraft(key, saved);
      setDraft(saved);
      setView(fresh);
      if (fresh.activity) onActivity?.(fresh.activity);
    } catch (cause) {
      if (
        alive.current &&
        activeOwner.current === owner &&
        version === loadVersion.current
      )
        setError(String(cause));
    } finally {
      if (
        alive.current &&
        activeOwner.current === owner &&
        version === loadVersion.current
      )
        setLoading(false);
    }
  }

  useEffect(() => {
    alive.current = true;
    storageKey.current = "";
    setView(null);
    setPreview(false);
    setRecording("idle");
    setSpeechSupported(!!recognitionConstructor());
    void load();
    return () => {
      alive.current = false;
      capture.current?.dispose();
      capture.current = null;
    };
    // A new node/revision gets an independent source-bound thread and draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner]);

  const disabled =
    loading || busy || sending.current || modeMismatch || !view?.can_write;

  function toggleRecording() {
    if (recording !== "idle") {
      capture.current?.stop();
      return;
    }
    const Recognition = recognitionConstructor();
    if (!Recognition || disabled || draft.pending) return;
    capture.current?.dispose();
    const currentOwner = owner;
    capture.current = attachDictation(
      new Recognition(),
      draft.text,
      (text) => {
        if (alive.current && activeOwner.current === currentOwner)
          updateDraft({ ...draft, text });
      },
      (state) => {
        if (alive.current && activeOwner.current === currentOwner)
          setRecording(state);
      },
      (message) => {
        if (alive.current && activeOwner.current === currentOwner)
          setError(message);
      },
    );
    capture.current.start();
  }

  async function send() {
    if (disabled || !view || !draft.text.trim() || recording !== "idle") return;
    capture.current?.dispose();
    capture.current = null;
    let request;
    try {
      request = requestForDraft(draft, view.target);
    } catch (cause) {
      setError(String(cause));
      return;
    }
    const key = storageKey.current;
    updateDraft({ ...draft, pending: request });
    setPreview(false);
    setBusy(true);
    sending.current = true;
    setError("");
    try {
      const result = await api<DiscussionResult>(base, request);
      const settled = settleDraft(
        { ...draft, pending: request },
        request.request_id,
        result.message.status,
      );
      // Save to the captured source key, never to a newly selected node.
      saveDiscussionDraft(key, settled);
      onSession(result.session);
      if (!alive.current || activeOwner.current !== owner) return;
      setDraft(settled);
      setView((current) =>
        current
          ? {
              ...current,
              messages: [
                ...current.messages.filter(
                  (item) => item.request_id !== request.request_id,
                ),
                result.message,
              ],
            }
          : current,
      );
      if (
        result.message.status === "failed" ||
        result.message.status === "uncertain"
      )
        setError(
          result.message.error ||
            "The request did not complete. Your draft is preserved.",
        );
      if (request.mode === "question") void load();
    } catch (cause) {
      if (alive.current && activeOwner.current === owner)
        setError(
          `${String(cause)} Your draft and request ID were preserved. Reload saved history before continuing.`,
        );
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      className="graph-discussion"
      aria-label={`Discussion for ${view?.title || nodeId}`}
    >
      <div className="discussion-heading">
        <div>
          <span className="eyebrow">SHAPE THIS SECTION</span>
          <h5>A little more of your vision.</h5>
        </div>
        <button
          className="text-button"
          onClick={() => void load()}
          disabled={busy || loading}
          aria-label="Reload saved discussion"
        >
          <RefreshCw size={14} />
        </button>
      </div>
      <p className="discussion-intro">
        Ask what this part means, or explain how you want it to work.
      </p>
      {session.mode === "demo" && (
        <p className="discussion-demo">Scripted demo · no model calls</p>
      )}
      {error && (
        <p className="plan-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="discussion-muted" role="status">
          Loading this section’s conversation…
        </p>
      ) : (
        <>
          {!!view?.messages.length ? (
            <ol
              className="discussion-history"
              aria-label="Section conversation"
            >
              {view.messages.map((message) => (
                <Message
                  key={message.id}
                  message={message}
                  useDirection={
                    !disabled && !draft.pending
                      ? (text) => {
                          updateDraft({ text, mode: "direction" });
                          setPreview(false);
                        }
                      : undefined
                  }
                />
              ))}
            </ol>
          ) : (
            <div className="discussion-empty">
              <MessageCircle size={21} />
              <p>This section has room for your ideas.</p>
              <small>
                Try “Why is this needed?” or describe a better flow.
              </small>
            </div>
          )}
          {!!view?.history?.length && (
            <details className="discussion-archives">
              <summary>Earlier revisions · read-only</summary>
              {view.history.map((thread, index) => (
                <div key={index}>
                  <strong>{thread.title}</strong>
                  <ol className="discussion-history">
                    {thread.messages.map((message) => (
                      <Message key={message.id} message={message} />
                    ))}
                  </ol>
                </div>
              ))}
            </details>
          )}
          {(!view?.can_write || modeMismatch) && (
            <p className="plan-notice">
              {modeMismatch
                ? "This session belongs to another server mode."
                : view?.reason ||
                  "This section is read-only. Continue in the current draft vision."}
            </p>
          )}
          <div
            className="discussion-mode"
            role="group"
            aria-label="Message purpose"
          >
            {(["question", "direction"] as const).map((mode) => (
              <button
                key={mode}
                aria-pressed={draft.mode === mode}
                disabled={disabled || !!draft.pending || recording !== "idle"}
                onClick={() => {
                  updateDraft({ ...draft, mode });
                  setPreview(false);
                }}
              >
                {mode === "question" ? "Ask about this" : "Add direction"}
              </button>
            ))}
          </div>
          <label className="sr-only" htmlFor={`discussion-${nodeId}`}>
            Your {draft.mode === "question" ? "question" : "direction"} for this
            section
          </label>
          <textarea
            id={`discussion-${nodeId}`}
            className="discussion-input"
            maxLength={6000}
            value={draft.text}
            disabled={disabled || !!draft.pending || recording !== "idle"}
            onChange={(event) => {
              updateDraft({ ...draft, text: event.target.value });
              setPreview(false);
            }}
            placeholder={
              draft.mode === "question"
                ? "What would you like to understand about this section?"
                : "Tell us how you imagine this part working…"
            }
            rows={4}
          />
          <div className="discussion-compose-actions">
            <span className="discussion-muted">{draft.text.length}/6000</span>
            <div>
              {speechSupported && (
                <button
                  className={`text-button discussion-mic ${recording !== "idle" ? "recording" : ""}`}
                  aria-label={
                    recording === "idle"
                      ? "Dictate section message"
                      : "Stop dictation"
                  }
                  disabled={
                    disabled || !!draft.pending || recording === "stopping"
                  }
                  onClick={toggleRecording}
                >
                  {recording !== "idle" ? (
                    <Square size={15} />
                  ) : (
                    <Mic size={16} />
                  )}
                  {recording === "idle"
                    ? "Dictate"
                    : recording === "stopping"
                      ? "Stopping…"
                      : "Stop"}
                </button>
              )}
              <button
                className="primary-button"
                disabled={
                  disabled || !draft.text.trim() || recording !== "idle"
                }
                onClick={() =>
                  draft.mode === "direction" ? setPreview(true) : void send()
                }
              >
                {busy ? (
                  <LoaderCircle size={14} className="spin" />
                ) : (
                  <ArrowUp size={15} />
                )}
                {draft.pending
                  ? "Check saved request"
                  : draft.mode === "direction"
                    ? "Review direction"
                    : "Ask question"}
              </button>
            </div>
          </div>
          {draft.pending && (
            <p className="plan-notice">
              This request has a saved ID. Checking it reuses that ID; uncertain
              requests are not automatically replayed.
            </p>
          )}
          {draft.pending &&
            view?.messages.some(
              (message) =>
                message.request_id === draft.pending!.request_id &&
                message.status === "uncertain",
            ) && (
              <div className="discussion-uncertain-choice">
                <p className="discussion-muted">
                  The earlier request may have been processed. Its exact text
                  stays in history. Starting a different message will not resend
                  it.
                </p>
                <button
                  className="secondary-button"
                  disabled={disabled}
                  onClick={() => {
                    const saved = view.messages.find(
                      (message) =>
                        message.request_id === draft.pending!.request_id,
                    );
                    updateDraft(startDifferentDraft(draft, saved));
                    setPreview(false);
                    setError("");
                  }}
                >
                  Start a different message
                </button>
              </div>
            )}
          {recording !== "idle" && (
            <p className="discussion-recording" role="status">
              Recording to this section only. Stop to edit the transcript.
              Nothing is sent automatically.
            </p>
          )}
          {!speechSupported && (
            <p className="discussion-muted">
              Dictation is unavailable in this browser. You can type your
              message.
            </p>
          )}
          {speechSupported && (
            <p className="discussion-muted">
              Dictation uses your browser’s speech service. Review the
              transcript before sending.
            </p>
          )}
          {preview && (
            <div
              className="discussion-preview"
              role="region"
              aria-label="Review direction before submitting"
            >
              <strong>Submit this direction for review?</strong>
              <blockquote>{draft.text}</blockquote>
              <p>
                This changes your requirements, makes the old plan stale, clears
                approvals and stops affected execution. A new plan still needs
                your review.
              </p>
              <div>
                <button
                  className="secondary-button"
                  onClick={() => setPreview(false)}
                >
                  Keep editing
                </button>
                <button
                  className="primary-button"
                  disabled={disabled}
                  onClick={() => void send()}
                >
                  Submit direction for review
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
