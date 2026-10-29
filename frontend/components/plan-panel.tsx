"use client";

import { useEffect, useRef, useState } from "react";
import { Download, GitBranch, LoaderCircle, ShieldCheck } from "lucide-react";
import { api, consumeEvents } from "@/lib/stream";
import {
  acceptPlanEvent,
  canApprovePlan,
  canExportPlan,
  canGeneratePlan,
  draftViews,
  type PlanCursor,
  type PlanDetail,
} from "@/lib/planning";
import type { Session } from "@/lib/types";
import { graphKey } from "@/lib/plan-graph";
import { PlanGraph } from "@/components/plan-graph";
import { GraphDiscussion } from "@/components/graph-discussion";
import type { DiscussionActivity } from "@/lib/discussion";
import { VaultWorkspace } from "@/components/vault-workspace";

export function PlanPanel({
  session,
  busy,
  setBusy,
  onSession,
  modeMismatch,
}: {
  session: Session;
  busy: boolean;
  setBusy: (value: boolean) => void;
  onSession: (session: Session) => void;
  modeMismatch: boolean;
}) {
  const [detail, setDetail] = useState<PlanDetail | null>(null);
  const [view, setView] = useState<"graph" | "human" | "engineering" | "vault">(
    "graph",
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const graphRequest = useRef(0);
  const base = `/sessions/${session.id}/plan`;
  const sourceKey = detail?.graph ? graphKey(detail.graph) : "intent";
  const displayedSource = useRef(sourceKey);
  displayedSource.current = sourceKey;
  const [activity, setActivity] = useState<{
    key: string;
    data: DiscussionActivity;
  }>({ key: "", data: {} });

  function reportSession(saved: Session) {
    if (alive.current && saved.id === session.id) {
      setDetail((previous) =>
        previous
          ? {
              ...previous,
              planning: saved.planning,
              estimated_usd: saved.estimated_usd,
            }
          : previous,
      );
      onSession(saved);
    }
  }

  useEffect(() => {
    alive.current = true;
    let disposed = false;
    setLoading(true);
    api<PlanDetail>(base)
      .then((data) => {
        if (!disposed) setDetail(data);
      })
      .catch((cause) => {
        if (!disposed) setError(String(cause));
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
      alive.current = false;
      controller.current?.abort();
      graphRequest.current++;
    };
  }, [base]);

  const state = detail?.planning ?? session.planning;
  const stale =
    state.status === "stale" ||
    (!!detail?.graph &&
      detail.graph.source.requirements_revision !== session.revision);
  const attempt = state.attempts.at(-1);
  const eligible = canGeneratePlan(
    detail,
    session.gate.ready,
    session.revision,
    session.approved_revision,
    modeMismatch,
  );
  const approvable = canApprovePlan(
    detail,
    session.id,
    session.revision,
    session.approved_revision,
    modeMismatch,
  );
  const exportable = canExportPlan(
    detail,
    session.id,
    session.revision,
    session.approved_revision,
    modeMismatch,
  );

  async function generate() {
    if (busy || !eligible || loading) return;
    setBusy(true);
    setError("");
    controller.current = new AbortController();
    let cursor: PlanCursor = { attempt_revision: 0, section_version: 0 };
    try {
      const response = await fetch(`/api${base}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        signal: controller.current.signal,
      });
      await consumeEvents(response, (event) => {
        if (
          !alive.current ||
          !acceptPlanEvent(event, session.id, session.revision, cursor)
        )
          return;
        cursor = {
          attempt_revision: event.attempt_revision!,
          section_version: event.section_version!,
        };
        const planning = event.planning!;
        const current = planning.attempts.at(-1);
        setDetail((previous) => ({
          session_id: session.id,
          requirements_revision: session.revision,
          attempt_limit: 2,
          pass_limit: 9,
          estimated_usd: 0,
          usage: [],
          execution_enabled: false,
          ...previous,
          planning,
          plan: null,
          partial: true,
          graph: null,
          views: current ? draftViews(current) : null,
        }));
        const request = ++graphRequest.current;
        void api<PlanDetail>(base)
          .then((fresh) => {
            if (
              alive.current &&
              graphRequest.current === request &&
              fresh.session_id === session.id &&
              fresh.requirements_revision === session.revision &&
              fresh.graph?.source.revision === current?.revision
            ) {
              setDetail((previous) =>
                previous ? { ...previous, graph: fresh.graph } : previous,
              );
            }
          })
          .catch(() => {
            /* The final reload below reports fetch failures. */
          });
        if (event.type === "plan_error")
          setError(
            event.message || "Planning failed. Accepted sections were saved.",
          );
      });
    } catch (cause) {
      if (alive.current)
        setError(
          cause instanceof Error ? cause.message : "Planning was interrupted.",
        );
    } finally {
      graphRequest.current++;
      try {
        const fresh = await api<PlanDetail>(base);
        const saved = await api<Session>(`/sessions/${session.id}`);
        if (alive.current) {
          setDetail(fresh);
          onSession(saved);
        }
      } catch (cause) {
        if (alive.current) setError(String(cause));
      }
      setBusy(false);
    }
  }

  async function approve() {
    if (busy || !approvable || !detail?.planning.active) return;
    setBusy(true);
    setError("");
    try {
      const approved = await api<PlanDetail>(
        `${base}/approve`,
        detail.planning.active,
      );
      if (alive.current) setDetail(approved);
      const saved = await api<Session>(`/sessions/${session.id}`);
      if (alive.current) onSession(saved);
    } catch (cause) {
      if (alive.current) setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="plan-panel">
      <div className="plan-intro">
        <span className="eyebrow">YOUR PROJECT, IN CONVERSATION</span>
        <h3>See the plan. Shape every part.</h3>
        <p>
          Select a section to ask questions, explain your vision, or dictate a
          better way forward. Your direction stays connected to the part it
          belongs to.
        </p>
        <div className="plan-badges">
          <span>
            {session.mode === "demo"
              ? "Scripted demo · no model calls"
              : "Live Nemotron planning"}
          </span>
          <span aria-live="polite">
            {stale ? "stale" : state.status.replaceAll("_", " ")}
          </span>
          {attempt && (
            <span>
              Revision {attempt.revision} · {attempt.passes.length}/
              {detail?.pass_limit ?? 9} passes reserved
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="plan-error" role="alert">
          {error}
        </div>
      )}
      {stale && (
        <p className="plan-notice">
          Requirements changed. This plan is stale; its approval was cleared.
          Previous work remains available for inspection.
        </p>
      )}
      {stale && detail?.graph && (
        <details className="draft-vision-current">
          <summary>Shape your current draft vision</summary>
          <GraphDiscussion
            session={session}
            nodeId="intent"
            busy={busy}
            setBusy={setBusy}
            onSession={reportSession}
            modeMismatch={modeMismatch}
          />
        </details>
      )}
      {attempt?.error && attempt.error !== error && (
        <p className="plan-notice">{attempt.error}</p>
      )}

      <div className="plan-actions">
        <button
          className="primary-button"
          disabled={busy || loading || !eligible}
          onClick={() => void generate()}
        >
          {busy ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <GitBranch size={15} />
          )}
          {state.status === "blocked" || state.status === "stale"
            ? "Retry planning"
            : state.active
              ? "Reload saved plan"
              : "Generate phase plan"}
        </button>
        {approvable && state.status !== "approved" && (
          <button
            className="secondary-button"
            disabled={busy}
            onClick={() => void approve()}
          >
            <ShieldCheck size={15} />
            Approve this revision
          </button>
        )}
        {exportable && !busy && (
          <a className="secondary-button" href={`/api${base}/bundle`}>
            <Download size={15} />
            Export instruction bundle
          </a>
        )}
      </div>
      {!session.gate.ready || session.approved_revision !== session.revision ? (
        <p className="plan-notice">
          Approve the current requirements playback before generating a plan.
        </p>
      ) : (
        detail &&
        !eligible &&
        state.status !== "planning" && (
          <p className="plan-notice">
            The planning attempt allowance is exhausted. Accepted sections and
            usage are preserved.
          </p>
        )
      )}

      {attempt?.outline && (
        <ol className="plan-phases" aria-label="Plan phase progress">
          {attempt.outline.phases.map((phase, index) => (
            <li key={phase.ref}>
              <span className="plan-phase-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <strong>{phase.title}</strong>
                <small>
                  {attempt.phases.some((p) => p.ref === phase.ref)
                    ? "Section validated"
                    : "Details pending"}
                </small>
              </div>
            </li>
          ))}
        </ol>
      )}

      <div className="plan-tabs" role="group" aria-label="Plan view">
        <button
          aria-pressed={view === "graph"}
          onClick={() => setView("graph")}
        >
          Project graph
        </button>
        <button
          aria-pressed={view === "vault"}
          onClick={() => setView("vault")}
        >
          Graph & notes
        </button>
        <button
          aria-pressed={view === "human"}
          onClick={() => setView("human")}
        >
          Vision & wireframes
        </button>
        <button
          aria-pressed={view === "engineering"}
          onClick={() => setView("engineering")}
        >
          Engineering & work packages
        </button>
      </div>
      <div hidden={view !== "vault"}>
        <VaultWorkspace
          key={session.id}
          session={session}
          canSeed={!!detail?.views}
          readOnly={modeMismatch || busy}
        />
      </div>
      {view !== "vault" &&
        (detail?.views || detail?.graph ? (
          <>
            <p className="plan-caption">
              {detail.partial
                ? "Draft sections · final validation and semantic review pending"
                : `Revision ${detail.plan?.revision} · one plan, connected views`}
            </p>
            {view === "graph" ? (
              detail.graph ? (
                <PlanGraph
                  key={graphKey(detail.graph)}
                  graph={detail.graph}
                  activity={activity.key === sourceKey ? activity.data : {}}
                  discussion={(node) => (
                    <GraphDiscussion
                      key={`${graphKey(detail.graph!)}:${node.id}`}
                      session={session}
                      nodeId={node.id}
                      source={detail.graph!.source}
                      onActivity={(data) => {
                        if (
                          alive.current &&
                          displayedSource.current === sourceKey
                        )
                          setActivity({ key: sourceKey, data });
                      }}
                      busy={busy}
                      setBusy={setBusy}
                      onSession={reportSession}
                      modeMismatch={modeMismatch}
                    />
                  )}
                  stale={modeMismatch || stale}
                />
              ) : (
                <p role="status" className="plan-notice">
                  Loading the graph of accepted sections…
                </p>
              )
            ) : (
              <pre
                className="plan-document"
                tabIndex={0}
                aria-label={
                  view === "human"
                    ? "Vision and wireframes"
                    : "Engineering plan"
                }
              >
                {detail.views?.[view]}
              </pre>
            )}
          </>
        ) : (
          <div className="draft-vision-workspace">
            <div className="draft-vision-map">
              <span className="eyebrow">DRAFT VISION</span>
              <div className="draft-root-connector" />
              <div className="draft-root-node">
                <GitBranch size={25} />
                <h4>Your project starts here.</h4>
                <p>
                  {session.ledger.find((item) => item.slot === "goal")?.text ||
                    session.turns[0]?.text ||
                    "Tell us what you want to make."}
                </p>
              </div>
              <p className="draft-vision-caption">
                Shape the vision now. Planning will add phases, subprojects and
                tasks.
              </p>
              <div className="draft-intent-notes">
                {session.ledger.slice(0, 4).map((item) => (
                  <span key={item.id}>{item.text}</span>
                ))}
              </div>
            </div>
            {loading ? (
              <p role="status">Loading your project…</p>
            ) : (
              <GraphDiscussion
                session={session}
                nodeId="intent"
                busy={busy}
                setBusy={setBusy}
                onSession={reportSession}
                modeMismatch={modeMismatch}
              />
            )}
          </div>
        ))}

      {attempt && (
        <details className="plan-footer">
          <summary>Planning passes and usage</summary>
          <ol>
            {attempt.passes.map((role) => (
              <li key={role}>
                <code>{role}</code> · reserved
              </li>
            ))}
          </ol>
          {detail?.usage.map((entry, index) => (
            <p key={index}>
              {entry.role}: {entry.input_tokens} input / {entry.output_tokens}{" "}
              output tokens, {entry.latency_ms} ms · $
              {entry.estimated_usd.toFixed(6)} estimated
            </p>
          ))}
        </details>
      )}
      <footer className="plan-footer">
        <span>
          {state.attempts.length}/{detail?.attempt_limit ?? 2} attempts used ·
          session estimate $
          {(detail?.estimated_usd ?? session.estimated_usd).toFixed(4)}
        </span>
        <p>
          Review proposed choices and checks before execution. The execution
          panel keeps context approval, worker permissions, and phase acceptance
          separate.
        </p>
      </footer>
    </div>
  );
}
