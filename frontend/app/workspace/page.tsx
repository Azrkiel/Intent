"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCheck,
  ChevronDown,
  Circle,
  Code2,
  Download,
  FileText,
  GitBranch,
  Layers3,
  LoaderCircle,
  MessageCircle,
  Mic,
  Plus,
  RotateCcw,
  Square,
  Terminal,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api, consumeEvents } from "@/lib/stream";
import { PlanPanel } from "@/components/plan-panel";
import { ExecutionPanel } from "@/components/execution-panel";
import { ClarityPanel } from "@/components/clarity-panel";
import { FrameworkReviewPanel } from "@/components/framework-review";
import { FIELD_LABELS, type NorthStarField } from "@/lib/clarity";
import {
  recognitionConstructor,
  speak,
  type SpeechRecognition,
} from "@/lib/speech";
import type {
  Health,
  LedgerItem,
  Lens,
  Question,
  Session,
  Slot,
} from "@/lib/types";

const EXAMPLE =
  "I want a habit tracker, no login, saved across my phone and laptop, and reminders should be automatic.";
const LENSES: { id: Lens; name: string; short: string }[] = [
  { id: "data", name: "Data & persistence", short: "Data" },
  { id: "identity", name: "Identity & access", short: "Access" },
  { id: "behaviour", name: "Behaviour words", short: "Behaviour" },
  { id: "contradictions", name: "Contradictions", short: "Conflicts" },
  { id: "edges", name: "Edges & failure", short: "Edges" },
  { id: "done-ness", name: "Done-ness", short: "Success" },
];
const SLOT_LABELS: Record<Slot, string> = {
  goal: "Clear goal",
  "core-flow": "Core flow",
  data: "Data & storage",
  access: "Who has access",
  "non-goals": "Scope boundaries",
  "success-criterion": "Success criterion",
};
type Summary = { id: string; title: string; mode: "demo" | "live" };
type View = "clarify" | "brief" | "plan" | "execution" | "build";

function Mark({ small = false }: { small?: boolean }) {
  return (
    <span className={`brand-mark ${small ? "small" : ""}`} aria-hidden="true">
      <img
        src="/brand/dragonfly-transparent.webp"
        alt=""
        width={44}
        height={44}
      />
    </span>
  );
}

function QuestionCard({
  question,
  onAnswer,
  disabled,
  past = false,
  onEdit,
}: {
  question: Question;
  onAnswer?: (value: string) => void;
  disabled?: boolean;
  past?: boolean;
  onEdit?: (value: string) => void;
}) {
  return (
    <div className={`question-card ${past ? "past" : ""}`}>
      <div className="question-eyebrow">
        <GitBranch size={13} />{" "}
        {LENSES.find((lens) => lens.id === question.lens)?.short ??
          (question.lens === "north-star" ? "North Star" : "Decision")}
      </div>
      <h3>{question.question}</h3>
      {!past && (
        <div className="answer-options">
          {question.options.map((option, i) => (
            <button
              key={option}
              disabled={disabled}
              onClick={() => onAnswer?.(option)}
            >
              <span className="option-letter">
                {String.fromCharCode(65 + i)}
              </span>
              <span>{option}</span>
              <ArrowUp size={13} />
            </button>
          ))}
        </div>
      )}
      {!past && question.suggestion && onEdit && (
        <button
          className="text-button"
          disabled={disabled}
          onClick={() => onEdit(question.options[0])}
        >
          Edit this draft
        </button>
      )}
      {!past && (
        <details className="question-why">
          <summary>
            Why it matters <ChevronDown size={12} />
          </summary>
          <p>{question.code_diff}</p>
        </details>
      )}
    </div>
  );
}

function LedgerEntry({ item }: { item: LedgerItem }) {
  return (
    <article className={`ledger-entry ${item.status}`} id={`ledger-${item.id}`}>
      <div className="ledger-meta">
        <span className="ledger-id">{item.id}</span>
        <span>{item.type.replaceAll("-", " ")}</span>
        <span className={`status ${item.status}`}>
          {item.status === "confirmed" ? (
            <Check size={10} />
          ) : (
            <Circle size={8} />
          )}
          {item.status}
        </span>
      </div>
      <p>{item.text}</p>
      {item.source ? (
        <details className="source-details">
          <summary>Source</summary>
          <div className="source-quote">
            “{item.source}” <span>· turn {item.turn}</span>
          </div>
        </details>
      ) : null}
    </article>
  );
}

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [history, setHistory] = useState<Summary[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("clarify");
  const [filter, setFilter] = useState("all");
  const [spoken, setSpoken] = useState(false);
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [lensStates, setLensStates] = useState<
    Partial<Record<Lens, "done" | "failed">>
  >({});
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const recognition = useRef<SpeechRecognition | null>(null);
  const initialized = useRef(false);
  const conversationScroll = useRef<HTMLDivElement>(null);
  const rankingDialog = useRef<HTMLDialogElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const remember = useCallback((data: Session) => {
    setSession(data);
    try {
      localStorage.setItem("prompt-caller-session", data.id);
    } catch {
      /* Storage is optional. */
    }
  }, []);

  const connect = useCallback(async () => {
    setError("");
    try {
      const config = await api<Health>("/health");
      setHealth(config);
      setHistory(await api<Summary[]>("/sessions"));
      let saved: string | null = null;
      try {
        saved = localStorage.getItem("prompt-caller-session");
      } catch {
        /* Use a fresh session. */
      }
      if (saved) {
        try {
          const restored = await api<Session>(`/sessions/${saved}`);
          remember(restored);
          return;
        } catch (cause) {
          if (
            !(cause instanceof Error) ||
            !cause.message.includes("Session not found")
          )
            throw cause;
        }
      }
      remember(await api<Session>("/sessions", {}));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Cannot reach the orchestrator. Run npm run dev.",
      );
    }
  }, [remember]);

  useEffect(() => {
    setVoiceAvailable(Boolean(recognitionConstructor()));
    if (!initialized.current) {
      initialized.current = true;
      void connect();
    }
    return () => {
      recognition.current?.abort();
    };
  }, [connect]);

  useEffect(() => {
    const pane = conversationScroll.current;
    pane?.scrollTo({ top: pane.scrollHeight, behavior: "smooth" });
  }, [session?.turns.length, session?.current_question?.id, busy]);

  useEffect(() => {
    if (spoken && session?.current_question && !busy) {
      speak(
        `${session.current_question.question} ${session.current_question.options.join(". Or, ")}`,
      );
    }
  }, [spoken, session?.current_question?.id, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (session?.build.status !== "running") return;
    let disposed = false;
    const timer = setInterval(() => {
      api<Session>(`/sessions/${session.id}`)
        .then((data) => {
          if (!disposed) remember(data);
        })
        .catch((cause) => {
          if (!disposed) setError(String(cause));
        });
    }, 1200);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [session?.id, session?.build.status, remember]);

  async function newSession() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      remember(await api<Session>("/sessions", {}));
      setHistory(await api<Summary[]>("/sessions"));
      setView("clarify");
      setInput("");
      setLensStates({});
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function loadSession(id: string) {
    if (busy) return;
    try {
      remember(await api<Session>(`/sessions/${id}`));
      setView("clarify");
      setError("");
    } catch (cause) {
      setError(String(cause));
    }
  }

  async function send(value = input) {
    if (!value.trim() || busy || !session) return;
    recognition.current?.stop();
    window.speechSynthesis?.cancel();
    const text = value.trim();
    setBusy(true);
    setError("");
    setStage("Listening to your idea…");
    setInput("");
    setInterim("");
    setLensStates({});
    setView("clarify");
    let receivedSavedState = false;
    try {
      const response = await fetch(`/api/sessions/${session.id}/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      await consumeEvents(response, (event) => {
        if (event.session) {
          remember(event.session);
          receivedSavedState = true;
        }
        if (event.message) setStage(event.message);
        if (event.type === "lens" && event.lens) {
          setLensStates((previous) => ({
            ...previous,
            [event.lens!]: event.failed ? "failed" : "done",
          }));
        }
      });
      setHistory(await api<Summary[]>("/sessions"));
    } catch (cause) {
      if (!receivedSavedState) setInput(text);
      setError(
        cause instanceof Error
          ? cause.message
          : "The request failed. Your saved ledger is available.",
      );
      try {
        remember(await api<Session>(`/sessions/${session.id}`));
      } catch {
        /* Retain the last state. */
      }
    } finally {
      setBusy(false);
      setStage("");
    }
  }

  async function clarityCall(
    path: string,
    body: Record<string, unknown>,
    message: string,
  ) {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    setStage(message);
    try {
      remember(
        await api<Session>(`/sessions/${session.id}/clarity/${path}`, {
          ...body,
          revision: session.revision,
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The request failed.");
    } finally {
      setBusy(false);
      setStage("");
    }
  }

  function correctField(field: NorthStarField) {
    setView("clarify");
    setInput(`About ${FIELD_LABELS[field]}: actually, `);
    setTimeout(() => textarea.current?.focus(), 50);
  }

  async function action(
    name: "playback" | "approve" | "compile" | "build" | "analyze",
  ) {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    setStage(
      name === "compile"
        ? "Compiling and checking every citation…"
        : name === "analyze"
          ? "Checking all six lenses again…"
          : "Updating your brief…",
    );
    try {
      let data = await api<Session>(
        `/sessions/${session.id}/${name}`,
        name === "approve" ? { revision: session.revision } : {},
      );
      remember(data);
      if (name === "approve") {
        setStage("Compiling and checking every citation…");
        data = await api<Session>(`/sessions/${session.id}/compile`, {});
        remember(data);
      }
      if (["playback", "approve", "compile"].includes(name)) setView("brief");
      if (name === "build") setView("build");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The request failed.");
    } finally {
      setBusy(false);
      setStage("");
    }
  }

  function startListening() {
    if (busy || listening || !session || session.build.status === "running")
      return;
    const Constructor = recognitionConstructor();
    if (!Constructor) {
      setError(
        "Speech recognition is unavailable in this browser. You can always type below.",
      );
      return;
    }
    window.speechSynthesis?.cancel();
    const instance = new Constructor();
    instance.lang = "en-US";
    instance.interimResults = true;
    instance.continuous = true;
    instance.onresult = (event) => {
      let final = "",
        draft = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript;
        else draft += event.results[i][0].transcript;
      }
      if (final)
        setInput((previous) => `${previous} ${final}`.trim().slice(0, 6000));
      setInterim(draft);
    };
    instance.onerror = (event) => {
      if (event.error !== "no-speech" && event.error !== "aborted") {
        setError(
          `Voice input: ${event.error}. Type your answer below to continue.`,
        );
      }
      setListening(false);
      setInterim("");
    };
    instance.onend = () => {
      setListening(false);
      setInterim("");
    };
    recognition.current = instance;
    try {
      instance.start();
      setListening(true);
      setError("");
    } catch {
      setError("The microphone could not start. Text input is available.");
    }
  }

  const hasTurns = Boolean(session?.turns.length);
  const modeMismatch = Boolean(
    session && health && session.mode !== health.mode,
  );
  const disabled =
    busy || !session || session.build.status === "running" || modeMismatch;
  const confirmed =
    session?.ledger.filter((item) => item.status === "confirmed").length || 0;
  const filteredLedger =
    session?.ledger.filter(
      (item) =>
        filter === "all" ||
        (filter === "open"
          ? item.status !== "confirmed"
          : item.status === filter),
    ) || [];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Intent home">
          <Mark />
          <span>
            INTENT<span className="brand-period">.</span>
          </span>
        </a>
        <button
          className="new-session"
          onClick={newSession}
          disabled={busy}
          aria-label="New intent"
        >
          <Plus size={17} />
          New intent
        </button>
        <nav className="workspace-nav" aria-label="Workspace">
          {(
            [
              ["clarify", "Conversation", MessageCircle],
              ["brief", "Build brief", FileText],
              ["plan", "Project graph", GitBranch],
              ["execution", "Codex execution", Terminal],
              ["build", "Build output", Code2],
            ] as const
          ).map(([id, label, Icon]) => (
            <button
              key={id}
              className="workspace-nav-link"
              aria-label={label}
              title={label}
              aria-current={view === id ? "page" : undefined}
              disabled={
                busy ||
                !session ||
                (id !== "clarify" && id !== "plan" && !hasTurns)
              }
              onClick={() => setView(id)}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        {history.some((item) => item.title !== "Untitled idea") && (
          <>
            <div className="sidebar-heading recent-heading">Recent</div>
            <div className="history">
              {history
                .filter((item) => item.title !== "Untitled idea")
                .slice(0, 5)
                .map((item) => (
                  <button
                    key={item.id}
                    className={item.id === session?.id ? "selected" : ""}
                    disabled={busy}
                    onClick={() => loadSession(item.id)}
                  >
                    <span className="history-dot" />
                    <span>{item.title}</span>
                  </button>
                ))}
            </div>
          </>
        )}
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <strong>Workspace</strong>
          </div>
          <div className="topbar-actions">
            <span
              className={`mode-badge ${(session?.mode ?? health?.mode) === "live" ? "live" : ""}`}
            >
              <span />
              {session || health
                ? (session?.mode ?? health?.mode) === "demo"
                  ? "Demo"
                  : "Live"
                : "Connecting"}
            </span>
            <button
              className="icon-button"
              title={
                spoken
                  ? "Turn spoken questions off"
                  : "Turn spoken questions on"
              }
              aria-label={
                spoken
                  ? "Turn spoken questions off"
                  : "Turn spoken questions on"
              }
              aria-pressed={spoken}
              onClick={() => {
                setSpoken(!spoken);
                if (spoken) window.speechSynthesis?.cancel();
              }}
            >
              {spoken ? <Volume2 size={17} /> : <VolumeX size={17} />}
            </button>
          </div>
        </header>

        <main
          id="main"
          className={`workspace ${view === "plan" ? "graph-workspace-page" : ""}`}
        >
          <h1 className="sr-only">Intent workspace</h1>

          <nav className="stepper" aria-label="Build stages">
            {(
              [
                ["clarify", "01", "Clarify", hasTurns],
                ["brief", "02", "Brief", Boolean(session?.brief)],
                ["build", "03", "Build", session?.build.status === "complete"],
              ] as const
            ).map(([id, number, label, completed], i) => (
              <div className="step-wrapper" key={id}>
                <button
                  className={`step ${view === id ? "current" : ""}`}
                  aria-current={view === id ? "step" : undefined}
                  disabled={id !== "clarify" && !hasTurns}
                  onClick={() => setView(id)}
                >
                  <span className="step-number">
                    {completed && view !== id ? <Check size={12} /> : number}
                  </span>
                  {label}
                </button>
                {i < 2 && <span className="step-line" />}
              </div>
            ))}
          </nav>

          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <div>
                {!health && (
                  <button onClick={() => void connect()}>Reconnect</button>
                )}
                {session && !session.analysis_complete && hasTurns && (
                  <button disabled={busy} onClick={() => action("analyze")}>
                    Retry analysis
                  </button>
                )}
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          )}
          {health?.mode === "live" && !health.models_configured && (
            <div className="error-banner">
              Live mode needs NEBIUS_API_KEY in the server .env file.
            </div>
          )}
          {modeMismatch && (
            <div className="error-banner">
              This conversation was recorded in {session?.mode} mode. Start a
              new conversation to use {health?.mode} mode.
            </div>
          )}

          <div
            className={`workspace-grid ${view !== "clarify" ? "review-grid" : ""} ${view === "plan" || view === "execution" ? "graph-focus" : ""}`}
          >
            <section className="conversation-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-icon">
                    <MessageCircle size={16} />
                  </span>
                  <h2>
                    {view === "clarify"
                      ? "Conversation"
                      : view === "brief"
                        ? "Brief"
                        : view === "plan"
                          ? "Project graph"
                          : view === "execution"
                            ? "Codex execution"
                            : "Build"}
                  </h2>
                </div>
                {view === "clarify" ? (
                  <button
                    className="text-button"
                    aria-expanded={transcriptOpen}
                    onClick={() => setTranscriptOpen(!transcriptOpen)}
                  >
                    <FileText size={13} />
                    {transcriptOpen ? "Close transcript" : "Transcript"}
                  </button>
                ) : null}
              </div>

              {view === "clarify" && (
                <>
                  <div
                    className={`conversation-content ${!hasTurns ? "empty" : ""}`}
                    ref={conversationScroll}
                  >
                    {!hasTurns ? (
                      <div className="welcome">
                        <div className="welcome-copy">
                          <h2>
                            What’s your
                            <br />
                            <span>intent?</span>
                          </h2>
                          <button
                            className="example-link"
                            disabled={disabled}
                            onClick={() => send(EXAMPLE)}
                          >
                            Try an example <ArrowRight size={14} />
                          </button>
                        </div>
                        <div className="welcome-graphic">
                          <img
                            src="/brand/dragonfly-transparent.webp"
                            alt="White engraved dragonfly with glitched, fragmented wings"
                            width={480}
                            height={480}
                            fetchPriority="high"
                          />
                        </div>
                      </div>
                    ) : (
                      <>
                        {session?.turns.map((turn) => {
                          const answered = session.questions.find(
                            (item) => item.turn === turn.number,
                          );
                          return (
                            <div key={turn.number} className="turn">
                              {answered && (
                                <div className="assistant-message">
                                  <Mark small />
                                  <QuestionCard
                                    question={answered.question}
                                    past
                                  />
                                </div>
                              )}
                              <div className="user-message">
                                <div>
                                  <p>{turn.text}</p>
                                  {turn.suggested && (
                                    <small className="drafted-label">
                                      {" "}
                                      · drafted by Intent, picked by you
                                    </small>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                        {!busy && session?.current_question && (
                          <div className="assistant-message">
                            <Mark small />
                            <QuestionCard
                              question={session.current_question}
                              onAnswer={send}
                              disabled={disabled}
                              onEdit={(value) => {
                                setInput(value);
                                setTimeout(() => textarea.current?.focus(), 50);
                              }}
                            />
                          </div>
                        )}
                        {!busy && session?.playback && !session.gate.ready && (
                          <div className="inline-playback">
                            <div>
                              <Volume2 size={15} />
                              <strong>Review</strong>
                            </div>
                            <p>{session.playback.sentences.join(" ")}</p>
                            <span>Corrections welcome.</span>
                          </div>
                        )}
                        {!busy && session?.gate.ready && (
                          <div className="ready-card">
                            <span className="ready-icon">
                              <CheckCheck size={22} />
                            </span>
                            <div>
                              <button
                                onClick={() => action("playback")}
                                disabled={busy}
                              >
                                Review brief
                                <ArrowRight size={15} />
                              </button>
                            </div>
                          </div>
                        )}
                        {busy && (
                          <div className="thinking" role="status">
                            <Mark small />
                            <div>
                              <span className="thinking-dots">
                                <i />
                                <i />
                                <i />
                              </span>
                              <p>{stage}</p>
                            </div>
                          </div>
                        )}
                        {!busy && session && !session.analysis_complete && (
                          <div className="analysis-warning">
                            Analysis incomplete. Your answers are saved.
                            <button onClick={() => action("analyze")}>
                              Retry analysis <RotateCcw size={12} />
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {transcriptOpen && (
                    <div className="raw-transcript">
                      <div className="eyebrow">Transcript</div>
                      {session?.turns.map((turn) => (
                        <p key={turn.number}>
                          <span>{String(turn.number).padStart(2, "0")}</span>
                          {turn.text}
                        </p>
                      ))}
                      {!hasTurns && <p>No messages yet.</p>}
                    </div>
                  )}
                  <div className="composer-container">
                    <div className={`composer ${listening ? "listening" : ""}`}>
                      <label className="sr-only" htmlFor="idea-input">
                        {hasTurns
                          ? "Your answer or correction"
                          : "Describe your idea"}
                      </label>
                      <textarea
                        ref={textarea}
                        id="idea-input"
                        value={input}
                        maxLength={6000}
                        disabled={disabled}
                        rows={2}
                        placeholder={
                          listening
                            ? "Listening…"
                            : hasTurns
                              ? "Your answer…"
                              : "Describe your idea…"
                        }
                        onChange={(event) => setInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            void send();
                          }
                        }}
                      />
                      {interim && <div className="interim">{interim}</div>}
                      <div className="composer-toolbar">
                        <div>
                          <button
                            className={`mic-button ${listening ? "recording" : ""}`}
                            disabled={disabled || !voiceAvailable}
                            title={
                              voiceAvailable
                                ? "Hold to talk, then send your words"
                                : "Voice unavailable in this browser; text always works"
                            }
                            aria-label="Hold to talk"
                            onPointerDown={(event) => {
                              event.currentTarget.setPointerCapture(
                                event.pointerId,
                              );
                              startListening();
                            }}
                            onPointerUp={() => recognition.current?.stop()}
                            onPointerCancel={() => recognition.current?.stop()}
                            onKeyDown={(event) => {
                              if (event.code === "Space" && !event.repeat) {
                                event.preventDefault();
                                startListening();
                              }
                            }}
                            onKeyUp={(event) => {
                              if (event.code === "Space") {
                                event.preventDefault();
                                recognition.current?.stop();
                              }
                            }}
                          >
                            {listening ? (
                              <Square size={15} />
                            ) : (
                              <Mic size={17} />
                            )}
                          </button>
                          <button
                            className="send-button"
                            disabled={disabled || !input.trim()}
                            aria-label="Send message"
                            onClick={() => send()}
                          >
                            {busy ? (
                              <LoaderCircle className="spin" size={17} />
                            ) : (
                              <ArrowUp size={19} />
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="composer-foot">
                      <span>
                        {session?.mode === "demo"
                          ? "Scripted demo · no model calls"
                          : "Sent to Nemotron"}
                      </span>
                      <span>
                        Enter <span className="keycap">↵</span>
                      </span>
                    </div>
                  </div>
                </>
              )}

              {view === "plan" && session && (
                <PlanPanel
                  key={`${session.id}:${session.revision}`}
                  session={session}
                  busy={busy}
                  setBusy={setBusy}
                  onSession={remember}
                  modeMismatch={modeMismatch}
                />
              )}

              {view === "execution" && session && (
                <ExecutionPanel
                  key={`${session.id}:${session.revision}`}
                  session={session}
                  busy={busy}
                  modeMismatch={modeMismatch}
                />
              )}

              {view === "brief" && (
                <div className="brief-content">
                  {!session?.playback &&
                  !session?.brief &&
                  !(
                    session?.clarity_version === 2 &&
                    session.clarity?.scenarios.length
                  ) ? (
                    <div className="review-empty">
                      <FileText size={32} />
                      <h2>Clarify your idea first.</h2>

                      <button
                        className="primary-button"
                        onClick={() => setView("clarify")}
                      >
                        Continue
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  ) : (
                    <>
                      {session?.clarity_version === 2 &&
                        !session.brief &&
                        Boolean(session.clarity?.scenarios.length) && (
                          <div className="playback-card scenario-card">
                            <div className="eyebrow">
                              <Check size={14} />
                              Review
                            </div>
                            <h2>Your scenarios.</h2>
                            {session.clarity!.scenarios.map((scenario) => (
                              <p key={scenario.id}>
                                <strong>{scenario.title}.</strong> Given{" "}
                                {scenario.given}, when {scenario.when}, then{" "}
                                {scenario.then}.
                              </p>
                            ))}
                            {(() => {
                              const filled = [
                                ...session
                                  .clarity!.claims.filter(
                                    (c) => c.status === "proposal",
                                  )
                                  .map((c) => c.text),
                                ...session
                                  .clarity!.decisions.filter(
                                    (d) => d.status === "delegated",
                                  )
                                  .map((d) => `${d.question} → ${d.outcome}`),
                              ];
                              return (
                                filled.length > 0 && (
                                  <>
                                    <h3>What I filled in for you</h3>
                                    <ul>
                                      {filled.map((text, i) => (
                                        <li key={i}>{text}</li>
                                      ))}
                                    </ul>
                                    <p className="framework-note">
                                      Approving includes these. Veto a choice in
                                      the Clarity panel, or choose Edit to
                                      change anything.
                                    </p>
                                  </>
                                )
                              );
                            })()}
                            <div className="playback-actions">
                              <button
                                className="secondary-button"
                                onClick={() => {
                                  setView("clarify");
                                  setInput("Actually, ");
                                  setTimeout(
                                    () => textarea.current?.focus(),
                                    50,
                                  );
                                }}
                              >
                                Edit
                              </button>
                              <button
                                className="primary-button"
                                disabled={busy || !session.gate.ready}
                                onClick={() => action("approve")}
                              >
                                {busy ? (
                                  <LoaderCircle size={15} className="spin" />
                                ) : (
                                  <Check size={15} />
                                )}
                                Approve scenarios
                              </button>
                            </div>
                          </div>
                        )}
                      {session?.playback && (
                        <div className="playback-card">
                          <div className="eyebrow">
                            <Volume2 size={14} />
                            Review
                          </div>
                          <h2>Your brief.</h2>
                          {session.playback.sentences.map((sentence, i) => (
                            <p key={i}>{sentence}</p>
                          ))}
                          <button
                            className="text-button"
                            onClick={() =>
                              speak(session.playback!.sentences.join(" "))
                            }
                          >
                            <Volume2 size={14} />
                            Read it aloud
                          </button>
                          {!session.brief && session.clarity_version !== 2 && (
                            <div className="playback-actions">
                              <button
                                className="secondary-button"
                                onClick={() => {
                                  setView("clarify");
                                  setInput("Actually, ");
                                  setTimeout(
                                    () => textarea.current?.focus(),
                                    50,
                                  );
                                }}
                              >
                                Edit
                              </button>
                              <button
                                className="primary-button"
                                disabled={busy || !session.gate.ready}
                                onClick={() => action("approve")}
                              >
                                {busy ? (
                                  <LoaderCircle size={15} className="spin" />
                                ) : (
                                  <Check size={15} />
                                )}
                                Approve brief
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                      {session?.brief && (
                        <>
                          <div className="spec-header">
                            <div>
                              <span className="eyebrow">CLAUDE.md</span>
                            </div>
                            <button
                              className="secondary-button"
                              onClick={() => setView("plan")}
                            >
                              <GitBranch size={14} />
                              Explore project graph
                            </button>
                            <a
                              className="secondary-button"
                              href={`/api/sessions/${session.id}/brief`}
                              download
                            >
                              <Download size={14} />
                              Export brief
                            </a>
                          </div>
                          <div className="comparison">
                            <div>
                              <div className="comparison-title">
                                <MessageCircle size={14} />
                                Your words
                              </div>
                              {session.turns.map((turn) => (
                                <p
                                  className="transcript-line"
                                  key={turn.number}
                                >
                                  <span>
                                    {String(turn.number).padStart(2, "0")}
                                  </span>
                                  {turn.text}
                                </p>
                              ))}
                            </div>
                            <div>
                              <div className="comparison-title">
                                <FileText size={14} />
                                Brief
                              </div>
                              {session.brief.lines.map((line, index) => (
                                <div className="spec-line" key={index}>
                                  <span className="spec-section">
                                    {line.section}
                                  </span>
                                  <p>{line.text}</p>
                                  <div>
                                    {line.ledger_ids.map((id) => (
                                      <a
                                        key={id}
                                        className="citation"
                                        href={`#ledger-${id}`}
                                        title={
                                          session.ledger.find(
                                            (item) => item.id === id,
                                          )?.source || "Unconfirmed"
                                        }
                                      >
                                        {id}
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="build-cta">
                            <div>
                              <span>
                                {session.mode === "demo"
                                  ? "Prebuilt demo · no agent run"
                                  : "Builds locally with Claude Code"}
                              </span>
                            </div>
                            <button
                              className="primary-button"
                              disabled={
                                busy ||
                                (session.mode === "live" &&
                                  !health?.build_enabled)
                              }
                              onClick={() => action("build")}
                            >
                              <Code2 size={16} />
                              {session.mode === "demo"
                                ? "Preview demo"
                                : "Build with Claude Code"}
                              <ArrowRight size={15} />
                            </button>
                          </div>
                          {session.mode === "live" &&
                            !health?.build_enabled && (
                              <p className="muted-note">
                                Enable ALLOW_CLAUDE_BUILD in the server .env
                                when you’re ready to run the agent.
                              </p>
                            )}
                        </>
                      )}
                      {busy && (
                        <div className="busy-line" role="status">
                          <LoaderCircle size={16} className="spin" />
                          {stage}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {view === "build" && (
                <div className="build-content">
                  {session?.build.status === "idle" ? (
                    <div className="review-empty">
                      <Code2 size={32} />
                      <h2>Approve your brief first.</h2>

                      <button
                        className="primary-button"
                        onClick={() =>
                          setView(session?.brief ? "brief" : "clarify")
                        }
                      >
                        {session?.brief ? "Brief" : "Clarify"}
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="build-heading">
                        <div>
                          <div className="eyebrow">
                            {session?.build.demo
                              ? "PREBUILT DEMO"
                              : "CLAUDE CODE · LOCAL RUN"}
                          </div>
                          <h2>
                            {session?.build.status === "running"
                              ? "Building…"
                              : session?.build.status === "failed"
                                ? "Build failed."
                                : "Build ready."}
                          </h2>
                        </div>
                        {session?.build.status === "running" ? (
                          <LoaderCircle className="spin" />
                        ) : session?.build.status === "complete" ? (
                          <CheckCheck />
                        ) : (
                          <RotateCcw />
                        )}
                      </div>
                      <div className="terminal">
                        <div>
                          <Terminal size={13} />
                          Build log<span>{session?.build.status}</span>
                        </div>
                        <pre aria-live="polite">
                          {session?.build.logs.join("\n\n") ||
                            "Starting the local agent…"}
                        </pre>
                      </div>
                      {session?.build.status === "complete" &&
                        session.build.preview_url && (
                          <>
                            <div className="preview-toolbar">
                              <span>
                                <span className="tiny-dot" />
                                {session.build.demo
                                  ? "Demo preview · scripted output"
                                  : "Generated app preview"}
                              </span>
                              <a
                                href={`${session.build.preview_url}?download=true`}
                                className="text-button"
                                download
                              >
                                <Download size={13} />
                                Download app
                              </a>
                            </div>
                            <iframe
                              className="app-preview"
                              title="Generated application preview"
                              src={session.build.preview_url}
                              sandbox="allow-scripts"
                            />
                            <p className="muted-note">
                              Preview blocks network and storage. Download to
                              run locally.
                            </p>
                          </>
                        )}
                      {session?.build.status === "failed" && (
                        <button
                          className="primary-button"
                          disabled={busy}
                          onClick={() => action("build")}
                        >
                          <RotateCcw size={14} />
                          Retry build
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}
            </section>

            <aside className="ledger-panel" aria-labelledby="vision-title">
              <div className="panel-header">
                <h2 id="vision-title">Vision</h2>
              </div>
              <div className="understanding">
                <div>
                  <span>Clarity</span>
                  <strong>
                    {session?.gate.percent || 0}
                    <small>%</small>
                  </strong>
                </div>
                <div
                  className="meter"
                  role="progressbar"
                  aria-label="Clarity"
                  aria-valuenow={session?.gate.percent || 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span style={{ width: (session?.gate.percent || 0) + "%" }} />
                </div>
                <details className="vision-details">
                  <summary>
                    Details <ChevronDown size={12} />
                  </summary>
                  <div className="slots">
                    {(Object.keys(SLOT_LABELS) as Slot[]).map((slot) => (
                      <span
                        key={slot}
                        className={
                          session?.gate.filled.includes(slot) ? "filled" : ""
                        }
                      >
                        {session?.gate.filled.includes(slot) ? (
                          <Check size={11} />
                        ) : (
                          <Circle size={9} />
                        )}
                        {SLOT_LABELS[slot]}
                      </span>
                    ))}
                  </div>
                </details>
              </div>
              {hasTurns && (
                <>
                  {session &&
                    (session.clarity_version === 2 ? (
                      <ClarityPanel
                        session={session}
                        busy={busy}
                        disabled={disabled}
                        onConfirm={(field, textHash) =>
                          void clarityCall(
                            "readback",
                            { field, text_hash: textHash },
                            "Checking the rest of your North Star…",
                          )
                        }
                        onCorrect={correctField}
                        onVeto={(decisionId) =>
                          void clarityCall(
                            "veto",
                            { decision_id: decisionId },
                            "Turning that choice into a question…",
                          )
                        }
                        onReaderVariation={(mode) =>
                          void clarityCall(
                            "reader-variation",
                            { mode },
                            "Changing the reader check…",
                          )
                        }
                        onRetry={() => void action("analyze")}
                      />
                    ) : (
                      <FrameworkReviewPanel
                        session={session}
                        busy={busy}
                        disabled={disabled}
                        onRetry={() => void action("analyze")}
                      />
                    ))}
                  <div
                    className="ledger-tabs"
                    role="group"
                    aria-label="Filter vision"
                  >
                    {[
                      ["all", "All", session?.ledger.length || 0],
                      ["confirmed", "Confirmed", confirmed],
                      [
                        "open",
                        "Open",
                        (session?.ledger.length || 0) - confirmed,
                      ],
                    ].map(([id, label, count]) => (
                      <button
                        key={id}
                        onClick={() => setFilter(String(id))}
                        className={filter === id ? "active" : ""}
                        aria-pressed={filter === id}
                      >
                        {label}
                        <span>{count}</span>
                      </button>
                    ))}
                  </div>
                  <div className="ledger-items">
                    {filteredLedger.length ? (
                      filteredLedger.map((item) => (
                        <LedgerEntry item={item} key={item.id} />
                      ))
                    ) : (
                      <p className="ledger-empty">No matches.</p>
                    )}
                  </div>
                  <div className="lenses-section">
                    <div className="lenses-heading">
                      <span>Angles</span>
                      {busy && <LoaderCircle size={12} className="spin" />}
                    </div>
                    <div className="lens-grid">
                      {LENSES.map((lens) => (
                        <span
                          key={lens.id}
                          className={
                            lensStates[lens.id] ||
                            (session?.analysis_complete ? "done" : "")
                          }
                          title={lens.name}
                        >
                          {lensStates[lens.id] === "done" ||
                          session?.analysis_complete ? (
                            <Check size={11} />
                          ) : (
                            <Circle size={9} />
                          )}
                          {lens.short}
                        </span>
                      ))}
                    </div>
                    {session?.current_question && (
                      <button
                        className="ranking-button"
                        onClick={() => rankingDialog.current?.showModal()}
                      >
                        <GitBranch size={13} />
                        Why this question?
                        <ArrowRight size={12} />
                      </button>
                    )}
                  </div>
                </>
              )}
            </aside>
          </div>
          <footer className="workspace-footer">
            {session?.mode === "live" && hasTurns && (
              <span>
                {session.usage.length} calls · {"$"}
                {session.estimated_usd.toFixed(3)} est.
              </span>
            )}
          </footer>
        </main>
      </div>

      <dialog className="ranking-dialog" ref={rankingDialog}>
        <div className="dialog-header">
          <div>
            <h2>Angles</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close question ranking"
            onClick={() => rankingDialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        <details className="ranking-method">
          <summary>Scoring</summary>
          <p>
            Impact = code divergence × uncertainty × cost to change. Each factor
            is 1–3. Divergence 1 is excluded.
          </p>
        </details>
        {session?.mode === "demo" && (
          <p className="demo-notice">Scripted demo scores</p>
        )}
        <div className="ranked-list">
          {session?.candidates.map((question, index) => (
            <article key={question.id}>
              <div className="rank-position">
                {String(index + 1).padStart(2, "0")}
              </div>
              <div>
                <div className="ranked-meta">
                  {question.lens}
                  <span>
                    {question.divergence} × {question.uncertainty} ×{" "}
                    {question.cost_to_change} ={" "}
                    <strong>{question.impact}</strong>
                  </span>
                </div>
                <h3>{question.question}</h3>
                <p>{question.code_diff}</p>
                {question.targets.map((id) => (
                  <span className="citation" key={id}>
                    {id}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
        {session?.rejected_candidates.length ? (
          <details className="rejected-list">
            <summary>
              {session.rejected_candidates.length} dropped or duplicate
              questions
            </summary>
            {session.rejected_candidates.map((q, i) => (
              <p key={i}>
                {q.question}
                <br />
                <small>
                  {q.code_diff} · divergence {q.divergence}
                </small>
              </p>
            ))}
          </details>
        ) : null}
        {session?.warnings.map((warning, i) => (
          <p className="warning-text" key={i}>
            {warning}
          </p>
        ))}
        {session?.gate.blockers.map((blocker, i) => (
          <p className="gate-blocker" key={i}>
            <Circle size={9} />
            {blocker}
          </p>
        ))}
        <button
          className="secondary-button"
          onClick={() => rankingDialog.current?.close()}
        >
          Close
          <ArrowDown size={14} />
        </button>
      </dialog>
    </div>
  );
}
