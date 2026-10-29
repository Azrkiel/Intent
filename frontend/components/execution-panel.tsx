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
  canApproveContext,
  canResumeContextPhase,
  samePlan,
  type Evidence,
  type ExecutionDetail,
  type ExecutionPhase,
  type ExecutionRun,
  type ExecutionContext,
  type ContextPackageOption,
} from "@/lib/execution";
import type { Session } from "@/lib/types";

const label = (status: string) => status.replaceAll("_", " ");

function ContextReview({
  context,
  detail,
  enabled,
  base,
  act,
}: {
  context: ExecutionContext;
  detail: ExecutionDetail;
  enabled: boolean;
  base: string;
  act: (path: string, body: unknown) => Promise<void>;
}) {
  const [inspected, setInspected] = useState(false);
  return (
    <div className="execution-context-review">
      <div className="execution-row">
        <h4>
          <ShieldCheck size={14} /> {context.package_id} · context review
        </h4>
        <span className="execution-status">
          {!context.current
            ? "Stale context"
            : context.approved
              ? "Context approved"
              : "Awaiting approval"}
        </span>
      </div>
      <p>
        Phase attempt {context.phase_attempt} ·{" "}
        {new TextEncoder().encode(context.text).byteLength.toLocaleString()}{" "}
        bytes. Approving this packet authorizes these instructions and inputs;
        starting or resuming remains a separate action.
      </p>
      <code className="execution-hash">
        Context SHA-256 {context.context_hash}
      </code>
      <code className="execution-hash">
        Packet SHA-256 {context.packet_hash}
      </code>
      <code className="execution-hash">Input commit {context.base_commit}</code>
      <details
        onToggle={(event) => {
          if (event.currentTarget.open) setInspected(true);
        }}
      >
        <summary>Read the exact worker context before approving</summary>
        <pre className="execution-code" tabIndex={0}>
          {context.text}
        </pre>
      </details>
      <details>
        <summary>Input documents and shared snapshots</summary>
        <ul>
          {Object.keys(context.documents).map((path) => (
            <li key={path}>
              <code>{path}</code>
            </li>
          ))}
        </ul>
        <pre className="execution-code" tabIndex={0}>
          {JSON.stringify(context.snapshots, null, 2)}
        </pre>
        <code className="execution-hash">
          Manifest SHA-256 {context.manifest_hash}
        </code>
      </details>
      <div className="plan-actions">
        {!context.approved && (
          <button
            className="secondary-button"
            disabled={
              !inspected || !canApproveContext(detail, context, enabled)
            }
            onClick={() =>
              void act(`/contexts/${context.context_hash}/approve`, {
                ...context.plan,
                packet_hash: context.packet_hash,
              })
            }
          >
            Approve this exact context
          </button>
        )}
        {context.approved && context.current && (
          <a
            className="secondary-button"
            href={`/api${base}/contexts/${context.context_hash}/bundle`}
          >
            Export scoped worker bundle
          </a>
        )}
      </div>
      {!context.approved && !inspected && context.current && (
        <p className="muted-note">
          Open the exact context to review its ancestor chain, scope, inputs,
          and handoff.
        </p>
      )}
      {!context.current && (
        <p className="muted-note">
          The plan, inputs, or execution state changed. Prepare a new context;
          this record stays available for inspection.
        </p>
      )}
    </div>
  );
}

function ContextPackageControls({
  option,
  detail,
  enabled,
  base,
  act,
}: {
  option: ContextPackageOption;
  detail: ExecutionDetail;
  enabled: boolean;
  base: string;
  act: (path: string, body: unknown) => Promise<void>;
}) {
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const publications = option.publication_options ?? [];
  const keyFor = (
    producer: string,
    name: string | null,
    version: string | null,
  ) => JSON.stringify([producer, name, version]);
  const choices = publications.map((publication) => ({
    producer_id: publication.producer_id,
    interface_name: publication.interface_name,
    interface_version: publication.interface_version,
    paths: (
      selected[
        keyFor(
          publication.producer_id,
          publication.interface_name,
          publication.interface_version,
        )
      ] ?? []
    ).filter((path) =>
      publication.artifacts.some((artifact) => artifact.path === path),
    ),
  }));
  const completeSelection = choices.every((choice) => choice.paths.length > 0);
  const contexts = (detail.contexts ?? []).filter(
    (context) =>
      context.package_id === option.id && samePlan(context.plan, detail.plan),
  );
  return (
    <section
      className="execution-context-package"
      aria-label={`Worker context ${option.id}`}
    >
      <h4>{option.id} · scope and inputs</h4>
      <p>
        Owned paths: <code>{option.owned_paths.join(", ")}</code>
      </p>
      {publications.map((publication) => {
        const groupKey = keyFor(
          publication.producer_id,
          publication.interface_name,
          publication.interface_version,
        );
        return (
          <fieldset
            className="execution-publication"
            key={groupKey}
            disabled={!enabled || !option.can_prepare}
          >
            <legend>
              Shared inputs from {publication.producer_id}
              {publication.interface_name
                ? ` · ${publication.interface_name}@${publication.interface_version}`
                : " · dependency outputs"}
            </legend>
            <p>
              Select the verified artifacts this subproject needs. Its
              producer’s task packet and private logs are excluded.
            </p>
            {publication.artifacts.length ? (
              publication.artifacts.map((artifact) => (
                <label key={artifact.path}>
                  <input
                    type="checkbox"
                    checked={(selected[groupKey] ?? []).includes(artifact.path)}
                    onChange={(event) =>
                      setSelected((previous) => ({
                        ...previous,
                        [groupKey]: event.target.checked
                          ? [...(previous[groupKey] ?? []), artifact.path]
                          : (previous[groupKey] ?? []).filter(
                              (path) => path !== artifact.path,
                            ),
                      }))
                    }
                  />
                  <span>
                    {artifact.path}
                    <code className="execution-hash">
                      SHA-256 {artifact.sha256}
                    </code>
                  </span>
                </label>
              ))
            ) : (
              <p>
                No published artifact candidates. This input blocks preparation.
              </p>
            )}
          </fieldset>
        );
      })}
      <div className="plan-actions">
        <button
          className="secondary-button"
          disabled={!enabled || !option.can_prepare || !completeSelection}
          onClick={() =>
            void act("/contexts/prepare", {
              ...detail.plan,
              package_id: option.id,
              publications: choices,
            })
          }
        >
          Prepare {option.id} context
        </button>
        {option.context_ready && (
          <span className="execution-context-ready">
            Current context approved
          </span>
        )}
      </div>
      {option.context_reason && (
        <p className="muted-note">{option.context_reason}</p>
      )}
      {!completeSelection && (
        <p className="muted-note">
          Select at least one verified artifact for each shared input.
        </p>
      )}
      {contexts.map((context) => (
        <ContextReview
          key={context.context_hash}
          context={context}
          detail={detail}
          enabled={enabled}
          base={base}
          act={act}
        />
      ))}
    </section>
  );
}

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
          start for the next phase. Review each eligible worker’s context before
          dispatch.
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
                {option.packages.map((packet) => (
                  <ContextPackageControls
                    key={`${packet.id}:${phase?.attempt ?? 1}`}
                    option={packet}
                    detail={detail}
                    enabled={enabled}
                    base={base}
                    act={act}
                  />
                ))}
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
                      {phase.status === "awaiting_context_review" && (
                        <button
                          className="primary-button"
                          disabled={
                            !canResumeContextPhase(detail, phase, enabled)
                          }
                          onClick={() =>
                            void act(`/phases/${phase.phase_id}/resume`, {
                              ...phase.plan,
                              ...(model.trim() ? { model: model.trim() } : {}),
                            })
                          }
                        >
                          Resume {phase.phase_id} with approved contexts
                        </button>
                      )}
                      {[
                        "running",
                        "verifying",
                        "awaiting_context_review",
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
