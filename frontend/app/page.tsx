"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  AudioLines,
  Check,
  CheckCheck,
  ChevronDown,
  Circle,
  Code2,
  Download,
  FileText,
  GitBranch,
  Headphones,
  Layers3,
  LoaderCircle,
  MessageCircle,
  Mic,
  Plus,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Square,
  Terminal,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api, consumeEvents } from "@/lib/stream";
import { PlanPanel } from "@/components/plan-panel";
import { ExecutionPanel } from "@/components/execution-panel";
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
    <span className={`brand-mark ${small ? "small" : ""}`}>
      <AudioLines size={small ? 17 : 23} strokeWidth={1.8} />
    </span>
  );
}

function QuestionCard({
  question,
  onAnswer,
  disabled,
  past = false,
}: {
  question: Question;
  onAnswer?: (value: string) => void;
  disabled?: boolean;
  past?: boolean;
}) {
  return (
    <div className={`question-card ${past ? "past" : ""}`}>
      <div className="question-eyebrow">
        <GitBranch size={13} />{" "}
        {LENSES.find((lens) => lens.id === question.lens)?.name}
        <span className="impact-badge">{question.impact} impact</span>
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
      {!past && (
        <details className="question-why">
          <summary>
            Why this changes the build <ChevronDown size={12} />
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
        <div className="source-quote">
          “{item.source}” <span>· turn {item.turn}</span>
        </div>
      ) : (
        <div className="source-quote no-source">
          No user quote · needs confirmation
        </div>
      )}
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
        <a className="brand" href="/">
          <Mark />
          <span>
            prompt caller<span className="brand-period">.</span>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-avatar">K</span>
          <div>
            Personal workspace<span>Local · on your machine</span>
          </div>
          <ChevronDown size={13} />
        </div>
        <button className="new-session" onClick={newSession} disabled={busy}>
          <Plus size={17} />
          New conversation<span>↗</span>
        </button>
        <div className="sidebar-heading">WORKSPACE</div>
        <button
          className={`sidebar-link ${view === "clarify" ? "active" : ""}`}
          onClick={() => setView("clarify")}
        >
          <MessageCircle size={16} />
          Conversation
          <ChevronDown size={12} />
        </button>
        <button
          className={`sidebar-link ${view === "brief" ? "active" : ""}`}
          onClick={() => setView("brief")}
          disabled={!hasTurns}
        >
          <FileText size={16} />
          Build brief{session?.brief && <span className="tiny-dot" />}
        </button>
        <button
          className={`sidebar-link project-graph-link ${view === "plan" ? "active" : ""}`}
          onClick={() => setView("plan")}
          disabled={!session}
        >
          <GitBranch size={16} />
          Project graph
        </button>
        <button
          className={`sidebar-link ${view === "execution" ? "active" : ""}`}
          onClick={() => setView("execution")}
          disabled={!hasTurns}
        >
          <Terminal size={16} />
          Codex execution
        </button>
        <button
          className={`sidebar-link ${view === "build" ? "active" : ""}`}
          onClick={() => setView("build")}
          disabled={!hasTurns}
        >
          <Code2 size={16} />
          Build output
        </button>
        <div className="sidebar-heading recent-heading">
          RECENT CONVERSATIONS
        </div>
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
          {!history.some((item) => item.title !== "Untitled idea") && (
            <p>Your next good idea starts here.</p>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="model-note">
            <span className="model-symbol">N</span>
            <div>
              Powered by Nemotron<span>Nano · Super · Ultra</span>
            </div>
            <span className="tiny-dot" />
          </div>
          <div className="sidebar-foot">
            <span>One good question at a time.</span>
            <Headphones size={14} />
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <Layers3 size={15} />
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>New build</strong>
          </div>
          <div className="topbar-actions">
            <span
              className={`mode-badge ${health?.mode === "live" ? "live" : ""}`}
            >
              <span />
              {health
                ? `${health.mode === "demo" ? "Demo" : "Live"} mode`
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
          {view === "plan" && <h1 className="sr-only">Project graph</h1>}
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="tiny-dot" />
                FROM A ROUGH IDEA TO A READY-TO-BUILD BRIEF
              </div>
              <h1>
                Your idea, made clear<span>.</span>
              </h1>
              <p>A focused conversation now. A much better build next.</p>
            </div>
            <div className="private-note">
              <ShieldCheck size={16} />
              <span>
                {session?.mode === "demo" ? "Local demo" : "Local workspace"}
                <small>
                  {session?.mode === "demo"
                    ? "No model calls or credits used"
                    : "Saved locally · sent to Nemotron"}
                </small>
              </span>
            </div>
          </div>

          <nav className="stepper" aria-label="Build stages">
            {(
              [
                ["clarify", "01", "Clarify the idea", hasTurns],
                ["brief", "02", "Review the brief", Boolean(session?.brief)],
                [
                  "build",
                  "03",
                  "Bring it to life",
                  session?.build.status === "complete",
                ],
              ] as const
            ).map(([id, number, label, completed], i) => (
              <div className="step-wrapper" key={id}>
                <button
                  className={`step ${view === id ? "current" : ""}`}
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
            <span className="session-meta">
              {session?.questions.length || 0} decisions clarified
            </span>
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
            className={`workspace-grid ${view !== "clarify" ? "review-grid" : ""} ${view === "plan" ? "graph-focus" : ""}`}
          >
            <section className="conversation-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-icon">
                    <MessageCircle size={16} />
                  </span>
                  <h2>
                    {view === "clarify"
                      ? "The conversation"
                      : view === "brief"
                        ? "Your build brief"
                        : view === "plan"
                          ? "Your project graph"
                          : view === "execution"
                            ? "Your phase execution"
                            : "The build workspace"}
                  </h2>
                </div>
                {view === "clarify" ? (
                  <button
                    className="text-button"
                    onClick={() => setTranscriptOpen(!transcriptOpen)}
                  >
                    <FileText size={13} />
                    {transcriptOpen ? "Hide transcript" : "Raw transcript"}
                  </button>
                ) : (
                  <span className="panel-caption">
                    {session?.brief
                      ? "Grounded in your words"
                      : "A clear brief starts with a clear idea"}
                  </span>
                )}
              </div>

              {view === "clarify" && (
                <>
                  <div
                    className={`conversation-content ${!hasTurns ? "empty" : ""}`}
                    ref={conversationScroll}
                  >
                    {!hasTurns ? (
                      <div className="welcome">
                        <div className="welcome-graphic">
                          <span className="orbit orbit-one" />
                          <span className="orbit orbit-two" />
                          <Mark />
                          <span className="orbit-spark">
                            <Sparkles size={14} />
                          </span>
                        </div>
                        <div className="welcome-kicker">
                          A LITTLE CLARITY GOES A LONG WAY
                        </div>
                        <h2>
                          What are you thinking
                          <br />
                          of building?
                        </h2>
                        <p>
                          Tell me the messy version. I’ll help you find the
                          details
                          <br className="desktop-break" /> that actually change
                          what gets built.
                        </p>
                        <button
                          className="example-card"
                          disabled={disabled}
                          onClick={() => send(EXAMPLE)}
                        >
                          <span className="example-icon">
                            <Sparkles size={17} />
                          </span>
                          <span>
                            <small>NEED A PLACE TO START?</small>“A habit
                            tracker, no login, synced across devices…”
                          </span>
                          <ArrowUp size={17} />
                        </button>
                        <div className="welcome-promises">
                          <span>
                            <Check size={12} />
                            One question at a time
                          </span>
                          <span>
                            <Check size={12} />
                            Your words stay the source
                          </span>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="conversation-start">
                          <Mark small />
                          <p>
                            I’ll turn your idea into a brief a coding agent can
                            build from. Let’s start with what’s on your mind.
                          </p>
                        </div>
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
                                  <div className="message-label">
                                    YOU{" "}
                                    <span>
                                      {turn.number === 1
                                        ? "The starting idea"
                                        : `Answer ${turn.number - 1}`}
                                    </span>
                                  </div>
                                  <p>{turn.text}</p>
                                </div>
                                <span className="user-avatar">K</span>
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
                            />
                          </div>
                        )}
                        {!busy && session?.playback && !session.gate.ready && (
                          <div className="inline-playback">
                            <div>
                              <Volume2 size={15} />
                              <strong>A quick check-in</strong>
                            </div>
                            <p>{session.playback.sentences.join(" ")}</p>
                            <span>
                              What did I get wrong? You can correct anything
                              below.
                            </span>
                          </div>
                        )}
                        {!busy && session?.gate.ready && (
                          <div className="ready-card">
                            <span className="ready-icon">
                              <CheckCheck size={22} />
                            </span>
                            <div>
                              <h3>We’ve got a clear picture.</h3>
                              <p>
                                The big decisions are covered. Let’s play it
                                back before we build.
                              </p>
                              <button
                                onClick={() => action("playback")}
                                disabled={busy}
                              >
                                Review my understanding
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
                            Your words are saved. Analysis needs to finish
                            before the build gate can open.
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
                      <div className="eyebrow">
                        RAW TRANSCRIPT · BEFORE CLARIFICATION
                      </div>
                      {session?.turns.map((turn) => (
                        <p key={turn.number}>
                          <span>{String(turn.number).padStart(2, "0")}</span>
                          {turn.text}
                        </p>
                      ))}
                      {!hasTurns && (
                        <p>Your original words will appear here.</p>
                      )}
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
                            ? "Listening… release the microphone when you’re done."
                            : hasTurns
                              ? "Your answer, a correction, or something else on your mind…"
                              : "I’ve been thinking about an app that…"
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
                        <div className="composer-hint">
                          <span
                            className={listening ? "recording-dot" : "tiny-dot"}
                          />
                          {listening
                            ? "Listening — your voice becomes editable text"
                            : "No perfect prompts needed."}
                        </div>
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
                          ? "Demo responses are scripted. No model is running."
                          : "Nemotron asks. You decide. The ledger remembers."}
                      </span>
                      <span>
                        Enter to send <span className="keycap">↵</span>
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
                  {!session?.playback && !session?.brief ? (
                    <div className="review-empty">
                      <FileText size={32} />
                      <h2>A brief built from understanding.</h2>
                      <p>
                        Answer the build-changing questions, then review a
                        playback of your idea.
                      </p>
                      <button
                        className="primary-button"
                        onClick={() => setView("clarify")}
                      >
                        Back to the conversation
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  ) : (
                    <>
                      {session?.playback && (
                        <div className="playback-card">
                          <div className="eyebrow">
                            <Volume2 size={14} />
                            LET’S MAKE SURE THIS SOUNDS LIKE YOU
                          </div>
                          <h2>Here’s what I heard.</h2>
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
                          {!session.brief && (
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
                                Make a correction
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
                                Approve & compile brief
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
                              <h3>From your words to a buildable brief.</h3>
                            </div>
                            <a
                              className="secondary-button"
                              href={`/api/sessions/${session.id}/brief`}
                              download
                            >
                              <Download size={14} />
                              Export brief
                            </a>
                            <button
                              className="text-button"
                              onClick={() => setView("plan")}
                            >
                              <GitBranch size={14} />
                              Explore project graph
                            </button>
                          </div>
                          <div className="comparison">
                            <div>
                              <div className="comparison-title">
                                <MessageCircle size={14} />
                                What you said
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
                                What gets built
                                <span className="citation-note">
                                  Every line has a source
                                </span>
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
                              <strong>
                                The brief is ready for Claude Code.
                              </strong>
                              <span>
                                {session.mode === "demo"
                                  ? "Demo mode will show a prebuilt example, without running the agent."
                                  : "Creates files in a separate local build directory."}
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
                                ? "Preview demo handoff"
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
                      <h2>Clarity comes before code.</h2>
                      <p>
                        Approve and compile your brief to hand it to Claude
                        Code.
                      </p>
                      <button
                        className="primary-button"
                        onClick={() =>
                          setView(session?.brief ? "brief" : "clarify")
                        }
                      >
                        Back to{" "}
                        {session?.brief ? "the brief" : "the conversation"}
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="build-heading">
                        <div>
                          <div className="eyebrow">
                            {session?.build.demo
                              ? "PREBUILT DEMO FIXTURE"
                              : "CLAUDE CODE · LOCAL RUN"}
                          </div>
                          <h2>
                            {session?.build.status === "running"
                              ? "Bringing the brief to life…"
                              : session?.build.status === "failed"
                                ? "The build needs attention."
                                : "Something you can try."}
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
                              The embedded preview blocks network access and
                              browser storage. Download the HTML to run it
                              separately.
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

            <aside className="ledger-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-icon">
                    <Layers3 size={16} />
                  </span>
                  <h2>Intent ledger</h2>
                </div>
                <span className="live-indicator">
                  <span />
                  LIVE
                </span>
              </div>
              <p className="ledger-description">
                A shared understanding, in your words.
              </p>
              <div className="understanding">
                <div>
                  <span>Understanding</span>
                  <strong>
                    {session?.gate.percent || 0}
                    <small>%</small>
                  </strong>
                </div>
                <div
                  className="meter"
                  role="progressbar"
                  aria-label="Understanding"
                  aria-valuenow={session?.gate.percent || 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span style={{ width: `${session?.gate.percent || 0}%` }} />
                </div>
                <p>
                  {session?.gate.ready
                    ? "The big questions are covered. Ready for your review."
                    : hasTurns
                      ? `${session?.gate.filled.length || 0} of 6 essentials clarified. Getting the details right.`
                      : "A clearer picture with every answer."}
                </p>
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
              </div>
              <div
                className="ledger-tabs"
                role="group"
                aria-label="Filter ledger"
              >
                {[
                  ["all", "All", session?.ledger.length || 0],
                  ["confirmed", "Confirmed", confirmed],
                  [
                    "open",
                    "To clarify",
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
                  <div className="ledger-empty">
                    <div className="ledger-placeholder">
                      <span />
                      <span />
                      <span />
                    </div>
                    <strong>
                      {hasTurns
                        ? "Nothing in this view yet."
                        : "Your idea starts taking shape here."}
                    </strong>
                    <p>
                      {hasTurns
                        ? "Confirmed decisions and open details will appear as you talk."
                        : "Goals, decisions, and open questions will find their place as we talk."}
                    </p>
                  </div>
                )}
              </div>
              <div className="lenses-section">
                <div className="lenses-heading">
                  <span>
                    <SlidersHorizontal size={13} />
                    SIX PERSPECTIVES, ONE QUESTION
                  </span>
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
                <button
                  className="ranking-button"
                  onClick={() => rankingDialog.current?.showModal()}
                  disabled={!hasTurns}
                >
                  <GitBranch size={13} />
                  See why this question comes next
                  <ArrowRight size={12} />
                </button>
              </div>
              <div className="ledger-footer">
                <ShieldCheck size={13} />
                <span>No quote, no confirmed requirement.</span>
              </div>
            </aside>
          </div>
          <footer className="workspace-footer">
            <span>
              <Mark small />
              Less guessing. More building.
            </span>
            <span>
              {session?.mode === "demo"
                ? "DETERMINISTIC DEMO"
                : "NEMOTRON → CLAUDE CODE"}
              <span className="footer-divider">/</span>
              {session?.usage.length || 0} calls · $
              {session?.estimated_usd.toFixed(3) || "0.000"} est.
            </span>
          </footer>
        </main>
      </div>

      <dialog className="ranking-dialog" ref={rankingDialog}>
        <div className="dialog-header">
          <div>
            <div className="eyebrow">GAP → RANK → ASK</div>
            <h2>One question. A reason to ask it.</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close question ranking"
            onClick={() => rankingDialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        <p className="dialog-intro">
          Impact = code divergence × uncertainty × cost to change later. Each
          factor is 1–3. Questions with divergence 1 are dropped.
        </p>
        {session?.mode === "demo" && (
          <p className="demo-notice">
            Scripted demo scores · not a live model evaluation
          </p>
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
          Back to the conversation
          <ArrowDown size={14} />
        </button>
      </dialog>
    </div>
  );
}
