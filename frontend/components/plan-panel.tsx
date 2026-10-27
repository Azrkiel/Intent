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
  const [view, setView] = useState<"human" | "engineering">("human");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const base = `/sessions/${session.id}/plan`;

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
    };
  }, [base]);

  const state = detail?.planning ?? session.planning;
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
          views: current ? draftViews(current) : null,
        }));
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
        <span className="eyebrow">FROM INTENT TO IMPLEMENTATION</span>
        <h3>One plan. Two ways to see it.</h3>
        <p>
          Review the vision and wireframes, then inspect the phases and work
          packages. Both views share one revision.
        </p>
        <div className="plan-badges">
          <span>
            {session.mode === "demo"
              ? "Scripted demo · no model calls"
              : "Live Nemotron planning"}
          </span>
          <span aria-live="polite">{state.status.replaceAll("_", " ")}</span>
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
      {state.status === "stale" && (
        <p className="plan-notice">
          Requirements changed. This plan is stale; its approval was cleared.
          Previous work remains available for inspection.
        </p>
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

      {detail?.views ? (
        <>
          <div className="plan-tabs" role="group" aria-label="Plan view">
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
          <p className="plan-caption">
            {detail.partial
              ? "Draft sections · final validation and semantic review pending"
              : `Revision ${detail.plan?.revision} · SHA-256 ${detail.plan?.content_hash}`}
          </p>
          <pre
            className="plan-document"
            tabIndex={0}
            aria-label={
              view === "human" ? "Vision and wireframes" : "Engineering plan"
            }
          >
            {detail.views[view]}
          </pre>
        </>
      ) : (
        <div className="plan-empty">
          <GitBranch size={30} />
          <h4>
            {loading ? "Loading your plan…" : "Make the next steps visible."}
          </h4>
          <p>
            Validated sections appear here as planning progresses. Approval and
            export become available after all checks pass.
          </p>
        </div>
      )}

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
          Codex execution is unavailable in this phase. Exported commands and
          proposed choices need review before execution.
        </p>
      </footer>
    </div>
  );
}
