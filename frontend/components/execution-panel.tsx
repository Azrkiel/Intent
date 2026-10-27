"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCheck,
  GitBranch,
  LoaderCircle,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { api } from "@/lib/stream";
import {
  acceptsExecutionResponse,
  canAnswerPermission,
  canRepairPhase,
  canReviewPhase,
  canStartPhase,
  samePlan,
  type Evidence,
  type ExecutionDetail,
  type ExecutionPhase,
  type ExecutionRun,
} from "@/lib/execution";
import type { Session } from "@/lib/types";

const label = (status: string) => status.replaceAll("_", " ");

function EvidenceView({
  evidence,
  base,
  phase,
}: {
  evidence: Partial<Evidence>;
  base?: string;
  phase?: ExecutionPhase;
}) {
  return (
    <div className="execution-evidence">
      <h4>Trusted checks</h4>
      <p className="muted-note">
        Git inspection verifies scope, artifacts and whitespace. Application
        behavior still needs review.
      </p>
      {evidence.checks?.length ? (
        <ul>
          {evidence.checks.map((check, i) => (
            <li key={i}>
              <strong>{check.exit_code === 0 ? "Passed" : "Failed"}</strong> ·{" "}
              <code>{check.argv.join(" ")}</code>
              <p>
                {check.log} · {check.policy}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p>No completed trusted checks.</p>
      )}
      <h4>Artifacts</h4>
      {Object.keys(evidence.artifacts ?? {}).length ? (
        <ul>
          {Object.entries(evidence.artifacts ?? {}).map(([path, hash]) => (
            <li key={path}>
              {base && phase?.review_hash ? (
                <a
                  download
                  href={`/api${base}/phases/${phase.phase_id}/artifacts/${path.split("/").map(encodeURIComponent).join("/")}?evidence_hash=${phase.review_hash}`}
                >
                  {path}
                </a>
              ) : (
                <span>{path}</span>
              )}
              <code className="execution-hash">SHA-256 {hash}</code>
            </li>
          ))}
        </ul>
      ) : (
        <p>No artifact evidence yet.</p>
      )}
      <h4>Unresolved decisions</h4>
      <p>{evidence.decisions?.join(" · ") || "None recorded."}</p>
      {!!evidence.exclusions?.length && (
        <>
          <h4>Scope exclusions to review</h4>
          <ul>
            {evidence.exclusions.map((value, i) => (
              <li key={i}>{value}</li>
            ))}
          </ul>
        </>
      )}
      <details>
        <summary>
          Changed files and diff ({evidence.changed_paths?.length ?? 0})
        </summary>
        <ul>
          {evidence.changed_paths?.map((path) => (
            <li key={path}>
              <code>{path}</code>
            </li>
          ))}
        </ul>
        <pre className="execution-code">
          {evidence.diff || "No inspected diff available."}
        </pre>
        {evidence.diff_truncated && (
          <p>
            Diff is truncated. Inspect the retained local checkout for the full
            change.
          </p>
        )}
      </details>
    </div>
  );
}

export function ExecutionPanel({
  session,
  busy,
  modeMismatch,
}: {
  session: Session;
  busy: boolean;
  modeMismatch: boolean;
}) {
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [pending, setPending] = useState(false);
  const [model, setModel] = useState("");
  const [notes, setNotes] = useState("");
  const [now, setNow] = useState(Date.now() / 1000);
  const requestSequence = useRef(0);
  const appliedSequence = useRef(0);
  const mounted = useRef(0);
  const mutation = useRef(false);
  const refresh = useRef<() => Promise<void>>(async () => {});
  const identity = session.planning.active;
  const planKey = identity ? JSON.stringify(identity) : "none";
  const base = `/sessions/${session.id}/execution`;

  useEffect(() => {
    let disposed = false;
    const generation = ++mounted.current;
    setDetail(null);
    setError("");
    const poll = async () => {
      const sequence = ++requestSequence.current;
      try {
        const result = await api<ExecutionDetail>(base);
        if (
          !disposed &&
          generation === mounted.current &&
          !mutation.current &&
          acceptsExecutionResponse(
            result,
            session.id,
            identity,
            sequence,
            appliedSequence.current,
            session.revision,
          )
        ) {
          appliedSequence.current = sequence;
          setDetail(result);
          setPollError("");
        }
      } catch (cause) {
        if (!disposed && generation === mounted.current)
          setPollError(String(cause));
      }
    };
    refresh.current = poll;
    void poll();
    const timer = setInterval(() => {
      setNow(Date.now() / 1000);
      if (!mutation.current) void poll();
    }, 2000);
    return () => {
      disposed = true;
      clearInterval(timer);
      mounted.current++;
    };
  }, [base, planKey, session.revision]); // identity's full value is captured by planKey

  const current =
    !busy &&
    !modeMismatch &&
    session.mode === "live" &&
    session.gate.ready &&
    session.approved_revision === session.revision &&
    session.planning.status === "approved" &&
    samePlan(identity, session.planning.approval) &&
    !!detail &&
    samePlan(detail.plan, identity) &&
    detail.requirements_revision === session.revision;
  const enabled = current && !pending;

  async function act(path: string, body: unknown) {
    if (pending || mutation.current) return;
    const generation = mounted.current;
    mutation.current = true;
    appliedSequence.current = ++requestSequence.current;
    setPending(true);
    setError("");
    try {
      await api(base + path, body);
    } catch (cause) {
      if (generation === mounted.current) setError(String(cause));
    } finally {
      mutation.current = false;
      if (generation === mounted.current) {
        setPending(false);
        await refresh.current();
      }
    }
  }

  function worker(run: ExecutionRun) {
    const owned = samePlan(run.plan, identity);
    const canAct = enabled && owned;
    return (
      <article className="execution-worker" key={run.id}>
        <div className="execution-row">
          <h4>
            <Terminal size={14} /> {run.package_id} · attempt{" "}
            {run.phase_attempt}
          </h4>
          <span className={`execution-status ${run.status}`}>
            {label(run.status)}
          </span>
        </div>
        <p>
          Owned paths: <code>{run.owned_paths.join(", ")}</code>
        </p>
        <p>
          Model:{" "}
          {run.selected_model ||
            run.model ||
            "Configured Codex default (not yet qualified)"}
        </p>
        <p>
          Account:{" "}
          {run.selected_model
            ? "Codex-managed ChatGPT login qualified for this attempt"
            : "Not yet qualified"}
        </p>
        <p>
          Observed Codex tokens: {run.token_usage.totalTokens ?? "not reported"}{" "}
          · turn {run.turn_status || "pending"}
        </p>
        {run.error && <p className="plan-error">{run.error}</p>}
        <div className="plan-actions">
          {["queued", "running", "verifying", "blocked"].includes(
            run.status,
          ) && (
            <button
              className="secondary-button"
              disabled={!canAct || run.cancel_requested}
              onClick={() => void act(`/${run.id}/cancel`, {})}
            >
              Cancel {run.package_id}
            </button>
          )}
          {["blocked", "cancelled"].includes(run.status) && !run.stale && (
            <button
              className="secondary-button"
              disabled={!canAct}
              onClick={() => void act(`/${run.id}/reconcile`, {})}
            >
              Inspect saved turn
            </button>
          )}
        </div>
        {run.approvals.map((request) => (
          <section
            className="execution-permission"
            key={request.id}
            aria-label="Permission request"
          >
            <h4>
              <ShieldCheck size={14} /> Permission · {request.status}
            </h4>
            <pre className="execution-code">
              {request.command || request.reason || "File change permission"}
            </pre>
            <p>
              {request.reason} · Expires{" "}
              {new Date(request.expires_at * 1000).toLocaleTimeString()}
            </p>
            <div className="plan-actions">
              {(["accept", "decline", "cancel"] as const).map((decision) => (
                <button
                  className="secondary-button"
                  key={decision}
                  disabled={!canAnswerPermission(run, request, canAct, now)}
                  onClick={() =>
                    void act(`/${run.id}/approvals/${request.id}`, {
                      generation: run.generation,
                      decision,
                    })
                  }
                >
                  {decision === "accept"
                    ? "Allow request"
                    : decision === "decline"
                      ? "Decline request"
                      : "Cancel request"}
                </button>
              ))}
            </div>
          </section>
        ))}
        <details>
          <summary>Worker log · claims from Codex</summary>
          <pre className="execution-code">
            {run.logs.join("\n") || "No messages yet."}
          </pre>
        </details>
        {Object.keys(run.evidence).length > 0 && (
          <details>
            <summary>Package evidence</summary>
            <EvidenceView evidence={run.evidence} />
          </details>
        )}
      </article>
    );
  }

  return (
    <div className="execution-panel">
      <div className="plan-intro">
        <div className="eyebrow">
          <GitBranch size={13} /> LOCAL CODEX EXECUTION
        </div>
        <h3>Build a phase. Review its evidence.</h3>
        <p>
          Each phase stops for your decision. Accepting it enables an explicit
          start for the next phase.
        </p>
      </div>
      {(error || pollError) && (
        <div className="plan-error" role="alert">
          {error || pollError}
        </div>
      )}
      {detail?.simulation && (
        <p className="plan-notice">
          <strong>SIMULATION · scripted workers, no provider calls.</strong>
        </p>
      )}
      {session.mode === "demo" && (
        <p className="plan-notice">
          Demo sessions cannot run Codex. The existing build preview is a
          prebuilt fixture.
        </p>
      )}
      {detail && !detail.execution_enabled && (
        <p className="plan-notice">
          Codex execution is disabled on this local server. Enable
          ALLOW_CODEX_EXECUTION to use the configured Codex login.
        </p>
      )}
      {!current && (
        <p className="muted-note">
          Current requirements and phase plan approval are required. Corrections
          invalidate execution and review actions.
        </p>
      )}
      {!detail ? (
        <p role="status">
          <LoaderCircle size={15} className="spin" /> Loading saved execution
          state…
        </p>
      ) : (
        <>
          <div className="plan-badges">
            <span>
              {detail.max_workers} worker{detail.max_workers === 1 ? "" : "s"}{" "}
              maximum
            </span>
            <span>{detail.verification_policy}</span>
            <span>
              Codex tokens tracked separately from Nemotron estimated dollars
            </span>
          </div>
          <label className="execution-label">
            Model override (optional)
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Use configured Codex default"
              maxLength={200}
              disabled={pending}
            />
          </label>
          <p className="muted-note">
            The worker checks the configured ChatGPT account, model
            availability, and usage limits before dispatch. No dollar cap or
            provider switch is inferred.
          </p>
          {detail.phase_options.map((option) => {
            const phase = detail.phases.find(
              (p) => p.phase_id === option.id && samePlan(p.plan, identity),
            );
            const review =
              phase &&
              detail.reviews.find((r) => r.evidence_hash === phase.review_hash);
            return (
              <section className="execution-phase" key={option.id}>
                <div className="execution-row">
                  <div>
                    <div className="eyebrow">
                      {option.id}
                      {phase && ` · ATTEMPT ${phase.attempt}`}
                    </div>
                    <h3>{option.title}</h3>
                  </div>
                  <span
                    className={`execution-status ${phase?.status || "queued"}`}
                  >
                    {phase ? label(phase.status) : "Not started"}
                  </span>
                </div>
                {!phase && (
                  <>
                    <ul>
                      {option.packages.map((p) => (
                        <li key={p.id}>
                          <code>{p.id}</code> · {p.owned_paths.join(", ")}
                        </li>
                      ))}
                    </ul>
                    <button
                      className="primary-button"
                      disabled={!canStartPhase(detail, option.id, enabled)}
                      onClick={() =>
                        void act(`/phases/${option.id}/start`, {
                          ...identity,
                          ...(model.trim() ? { model: model.trim() } : {}),
                        })
                      }
                    >
                      Start {option.id}
                    </button>
                    {!option.can_start && (
                      <p className="muted-note">
                        {option.reason ||
                          "Earlier phases require explicit acceptance."}
                      </p>
                    )}
                  </>
                )}
                {phase && (
                  <>
                    {phase.error && <p className="plan-error">{phase.error}</p>}
                    {phase.stale && (
                      <p className="plan-error">
                        This phase belongs to stale requirements. Its work is
                        retained for inspection.
                      </p>
                    )}
                    {detail.runs
                      .filter(
                        (r) =>
                          samePlan(r.plan, phase.plan) &&
                          r.package_id.split("-W")[0] === phase.phase_id &&
                          r.phase_attempt === phase.attempt,
                      )
                      .reverse()
                      .map(worker)}
                    {review && (
                      <>
                        <div className="execution-review">
                          <h4>
                            <CheckCheck size={15} /> Phase review evidence
                          </h4>
                          <code className="execution-hash">
                            Review {review.evidence_hash}
                          </code>
                          <code className="execution-hash">
                            Staging {review.staging_commit}
                          </code>
                          <EvidenceView
                            evidence={review.evidence}
                            base={base}
                            phase={phase}
                          />
                        </div>
                        <label className="execution-label">
                          Review notes (optional)
                          <textarea
                            maxLength={2000}
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            disabled={pending}
                          />
                        </label>
                        <div className="plan-actions">
                          <button
                            className="primary-button"
                            disabled={!canReviewPhase(detail, phase, enabled)}
                            onClick={() =>
                              void act(`/phases/${phase.phase_id}/review`, {
                                ...phase.plan,
                                evidence_hash: phase.review_hash,
                                decision: "accept",
                                notes,
                              })
                            }
                          >
                            Accept {phase.phase_id}
                          </button>
                          <button
                            className="secondary-button"
                            disabled={!canReviewPhase(detail, phase, enabled)}
                            onClick={() =>
                              void act(`/phases/${phase.phase_id}/review`, {
                                ...phase.plan,
                                evidence_hash: phase.review_hash,
                                decision: "reject",
                                notes,
                              })
                            }
                          >
                            Reject {phase.phase_id}
                          </button>
                        </div>
                      </>
                    )}
                    <div className="plan-actions">
                      {[
                        "running",
                        "verifying",
                        "awaiting_phase_review",
                        "blocked",
                      ].includes(phase.status) &&
                        !phase.promotion_intent && (
                          <button
                            className="secondary-button"
                            disabled={!enabled}
                            onClick={() =>
                              void act(
                                `/phases/${phase.phase_id}/cancel`,
                                phase.plan,
                              )
                            }
                          >
                            Cancel phase {phase.phase_id}
                          </button>
                        )}
                      {["blocked", "cancelled"].includes(phase.status) && (
                        <button
                          className="secondary-button"
                          disabled={!canRepairPhase(detail, phase, enabled)}
                          onClick={() =>
                            void act(`/phases/${phase.phase_id}/repair`, {
                              ...phase.plan,
                              attempt: phase.attempt,
                              evidence_hash: phase.review_hash,
                              ...(model.trim() ? { model: model.trim() } : {}),
                            })
                          }
                        >
                          Repair {phase.phase_id} with new attempts
                        </button>
                      )}
                      {phase.status === "blocked" && (
                        <button
                          className="secondary-button"
                          disabled={!enabled || phase.stale}
                          onClick={() =>
                            void act(`/phases/${phase.phase_id}/reconcile`, {
                              ...phase.plan,
                              evidence_hash: phase.review_hash,
                            })
                          }
                        >
                          Reconcile phase {phase.phase_id}
                        </button>
                      )}
                    </div>
                    {!!phase.review_notes && (
                      <p>Review notes: {phase.review_notes}</p>
                    )}
                  </>
                )}
              </section>
            );
          })}
          {detail.runs.some(
            (r) =>
              !samePlan(r.plan, identity) ||
              detail.phases.some(
                (p) =>
                  samePlan(p.plan, r.plan) &&
                  p.phase_id === r.package_id.split("-W")[0] &&
                  p.attempt !== r.phase_attempt,
              ),
          ) && (
            <details className="execution-history">
              <summary>Retained attempts from earlier reviews or plans</summary>
              {detail.runs
                .filter(
                  (r) =>
                    !samePlan(r.plan, identity) ||
                    detail.phases.some(
                      (p) =>
                        samePlan(p.plan, r.plan) &&
                        p.phase_id === r.package_id.split("-W")[0] &&
                        p.attempt !== r.phase_attempt,
                    ),
                )
                .map(worker)}
            </details>
          )}
          <p className="muted-note">
            Generated source and check evidence do not establish a running
            backend, deployment, or cross-device sync. Non-HTML projects have no
            live app preview here.
          </p>
        </>
      )}
    </div>
  );
}
