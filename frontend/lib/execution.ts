import type { PlanIdentity } from "./planning";

export interface Permission {
  id: string;
  generation: string;
  thread_id: string;
  turn_id: string;
  status: string;
  expires_at: number;
  command?: string;
  reason?: string;
}
export interface CheckResult {
  argv: string[];
  exit_code: number | null;
  policy: string;
  log: string;
  expected: string;
}
export interface Evidence {
  checks: CheckResult[];
  artifacts: Record<string, string>;
  changed_paths: string[];
  decisions: string[];
  exclusions: string[];
  diff: string;
  diff_truncated: boolean;
  provenance: string;
}
export interface ExecutionRun {
  id: string;
  plan: PlanIdentity;
  package_id: string;
  phase_attempt: number;
  status:
    "queued" | "running" | "verifying" | "integrated" | "blocked" | "cancelled";
  stale: boolean;
  cancel_requested: boolean;
  owned_paths: string[];
  thread_id: string | null;
  turn_id: string | null;
  generation: string | null;
  turn_status: string | null;
  dispatch_intent: string | null;
  model: string | null;
  selected_model: string | null;
  approvals: Permission[];
  logs: string[];
  changed_paths: string[];
  token_usage: Record<string, number>;
  evidence: Partial<Evidence>;
  error: string | null;
  context_hash?: string | null;
  packet_hash?: string | null;
}
export interface ExecutionPhase {
  id: string;
  plan: PlanIdentity;
  phase_id: string;
  attempt: number;
  status:
    | "running"
    | "verifying"
    | "awaiting_phase_review"
    | "awaiting_context_review"
    | "accepted"
    | "blocked"
    | "cancelled";
  stale: boolean;
  review_hash: string | null;
  promotion_intent: string | null;
  integration_intent: string | null;
  staging_commit: string | null;
  evidence: Partial<Evidence>;
  error: string | null;
  review_notes: string;
}
export interface PhaseReview {
  evidence_hash: string;
  plan: PlanIdentity;
  phase_id: string;
  phase_execution_id: string;
  attempt: number;
  staging_commit: string;
  package_attempt_ids: string[];
  evidence: Evidence;
}
export interface ExecutionDetail {
  session_id: string;
  requirements_revision: number;
  plan: PlanIdentity | null;
  runs: ExecutionRun[];
  phases: ExecutionPhase[];
  reviews: PhaseReview[];
  execution_enabled: boolean;
  phase_acceptance_enabled: boolean;
  simulation: boolean;
  max_workers: number;
  verification_policy: string;
  contexts?: ExecutionContext[];
  phase_options: {
    id: string;
    title: string;
    packages: ContextPackageOption[];
    can_start: boolean;
    reason: string;
  }[];
}

export interface PublicationOption {
  producer_id: string;
  interface_name: string | null;
  interface_version: string | null;
  artifacts: { path: string; sha256: string }[];
}
export interface ContextPackageOption {
  id: string;
  owned_paths: string[];
  can_prepare?: boolean;
  context_ready?: boolean;
  context_reason?: string;
  publication_options?: PublicationOption[];
}
export interface ExecutionContext {
  plan: PlanIdentity;
  package_id: string;
  phase_attempt: number;
  base_commit: string;
  context_hash: string;
  packet_hash: string;
  manifest_hash: string;
  review_hash: string;
  approved: boolean;
  current: boolean;
  text: string;
  documents: Record<string, string>;
  snapshots: Record<string, unknown>[];
}

export function canApproveContext(
  detail: ExecutionDetail,
  context: ExecutionContext,
  current: boolean,
): boolean {
  const phaseId = context.package_id.split("-W")[0];
  const phase = detail.phases.find(
    (candidate) =>
      candidate.phase_id === phaseId && samePlan(candidate.plan, context.plan),
  );
  return (
    current &&
    detail.execution_enabled &&
    context.current === true &&
    !context.approved &&
    /^[0-9a-f]{64}$/.test(context.packet_hash) &&
    /^[0-9a-f]{64}$/.test(context.context_hash) &&
    samePlan(context.plan, detail.plan) &&
    detail.requirements_revision === context.plan.requirements_revision &&
    (phase
      ? phase.attempt === context.phase_attempt &&
        !phase.stale &&
        !phase.integration_intent &&
        !phase.promotion_intent &&
        ["running", "awaiting_context_review"].includes(phase.status)
      : context.phase_attempt === 1) &&
    !detail.runs.some(
      (run) =>
        samePlan(run.plan, context.plan) &&
        run.package_id === context.package_id &&
        run.phase_attempt === context.phase_attempt,
    )
  );
}

export function canResumeContextPhase(
  detail: ExecutionDetail,
  phase: ExecutionPhase,
  current: boolean,
): boolean {
  return (
    current &&
    detail.execution_enabled &&
    phase.status === "awaiting_context_review" &&
    !phase.stale &&
    !phase.integration_intent &&
    !phase.promotion_intent &&
    samePlan(phase.plan, detail.plan) &&
    !!detail.phase_options
      .find((option) => option.id === phase.phase_id)
      ?.packages.some((option) => option.context_ready === true)
  );
}

export function samePlan(
  a: PlanIdentity | null,
  b: PlanIdentity | null,
): boolean {
  return (
    !!a &&
    !!b &&
    a.plan_id === b.plan_id &&
    a.revision === b.revision &&
    a.content_hash === b.content_hash &&
    a.requirements_revision === b.requirements_revision
  );
}
export function acceptsExecutionResponse(
  data: ExecutionDetail,
  sessionId: string,
  plan: PlanIdentity | null,
  sequence: number,
  applied: number,
  requirementsRevision = plan?.requirements_revision,
): boolean {
  return (
    data.session_id === sessionId &&
    sequence >= applied &&
    (requirementsRevision === undefined ||
      data.requirements_revision === requirementsRevision) &&
    (plan ? samePlan(data.plan, plan) : data.plan === null)
  );
}
export function canStartPhase(
  detail: ExecutionDetail | null,
  phaseId: string,
  current: boolean,
): boolean {
  if (!detail || !current || !detail.execution_enabled || !detail.plan)
    return false;
  const index = detail.phase_options.findIndex((p) => p.id === phaseId);
  return (
    index >= 0 &&
    detail.phase_options[index].can_start &&
    !detail.phases.some(
      (p) => p.phase_id === phaseId && samePlan(p.plan, detail.plan),
    ) &&
    detail.phases
      .filter((p) => samePlan(p.plan, detail.plan))
      .every(
        (p) => p.status === "accepted" && !p.stale && !p.promotion_intent,
      ) &&
    detail.phase_options
      .slice(0, index)
      .every((option) =>
        detail.phases.some(
          (p) =>
            p.phase_id === option.id &&
            samePlan(p.plan, detail.plan) &&
            p.status === "accepted" &&
            !p.stale &&
            !p.promotion_intent,
        ),
      )
  );
}
export function canReviewPhase(
  detail: ExecutionDetail,
  phase: ExecutionPhase,
  current: boolean,
): boolean {
  return (
    current &&
    detail.execution_enabled &&
    detail.phase_acceptance_enabled &&
    phase.status === "awaiting_phase_review" &&
    !phase.stale &&
    !phase.promotion_intent &&
    !phase.integration_intent &&
    samePlan(phase.plan, detail.plan) &&
    detail.reviews.some(
      (r) =>
        r.evidence_hash === phase.review_hash &&
        r.phase_execution_id === phase.id &&
        r.attempt === phase.attempt &&
        r.phase_id === phase.phase_id &&
        samePlan(r.plan, phase.plan),
    )
  );
}
export function canAnswerPermission(
  run: ExecutionRun,
  request: Permission,
  current: boolean,
  now = Date.now() / 1000,
): boolean {
  return (
    current &&
    run.status === "running" &&
    !run.stale &&
    !run.cancel_requested &&
    request.status === "pending" &&
    request.expires_at > now &&
    request.generation === run.generation &&
    request.thread_id === run.thread_id &&
    request.turn_id === run.turn_id &&
    run.approvals.some((p) => p.id === request.id)
  );
}
export function canRepairPhase(
  detail: ExecutionDetail,
  phase: ExecutionPhase,
  current: boolean,
): boolean {
  return (
    current &&
    detail.execution_enabled &&
    samePlan(phase.plan, detail.plan) &&
    ["blocked", "cancelled"].includes(phase.status) &&
    !phase.stale &&
    !phase.promotion_intent &&
    !phase.integration_intent &&
    detail.runs
      .filter(
        (r) =>
          samePlan(r.plan, phase.plan) &&
          r.package_id.split("-W")[0] === phase.phase_id &&
          r.phase_attempt === phase.attempt,
      )
      .every(
        (r) =>
          !["queued", "running", "verifying"].includes(r.status) &&
          !r.dispatch_intent &&
          (!r.thread_id ||
            ["completed", "failed", "interrupted"].includes(
              r.turn_status ?? "",
            )),
      )
  );
}
