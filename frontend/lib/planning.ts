import type { PlanGraphData } from "./plan-graph";

export interface PlanIdentity {
  plan_id: string;
  revision: number;
  content_hash: string;
  requirements_revision: number;
}
export interface PlanStatement {
  text: string;
  ledger_ids: string[];
  status: "confirmed" | "proposal" | "unresolved";
}
export interface PlanOutline {
  vision: PlanStatement;
  journeys: PlanStatement[];
  specification: PlanStatement[];
  common_rules: PlanStatement[];
  choices: PlanStatement[];
  architecture: string;
  phases: { ref: string; title: string; depends_on: string[] }[];
  screens: { ref: string; title: string; states: string[] }[];
}
export interface PlanAttempt {
  plan_id: string;
  revision: number;
  requirements_revision: number;
  passes: string[];
  outline: PlanOutline | null;
  screens: {
    ref: string;
    purpose: PlanStatement;
    wireframes: Record<string, string>;
  }[];
  phases: {
    ref: string;
    id: string;
    goal: PlanStatement;
    flow: string;
    packages: { id: string; ref: string }[];
  }[];
  error: string | null;
}
export interface PlanningState {
  status:
    "draft" | "planning" | "review_ready" | "approved" | "blocked" | "stale";
  attempts: PlanAttempt[];
  active: PlanIdentity | null;
  approval: PlanIdentity | null;
}
export interface PlanDetail {
  session_id: string;
  requirements_revision: number;
  planning: PlanningState;
  plan: {
    id: string;
    revision: number;
    content_hash: string;
    requirements_revision: number;
  } | null;
  views: { human: string; engineering: string } | null;
  graph?: PlanGraphData | null;
  partial: boolean;
  execution_enabled: false;
  attempt_limit: number;
  pass_limit: number;
  estimated_usd: number;
  usage: {
    role: string;
    input_tokens: number;
    output_tokens: number;
    estimated_usd: number;
    latency_ms: number;
  }[];
}
export interface PlanEvent {
  session_id?: string;
  requirements_revision?: number;
  attempt_revision?: number;
  section_version?: number;
  planning?: PlanningState;
}
export interface PlanCursor {
  attempt_revision: number;
  section_version: number;
}

export function acceptPlanEvent(
  event: PlanEvent,
  sessionId: string,
  revision: number,
  cursor: PlanCursor,
): boolean {
  return (
    event.session_id === sessionId &&
    event.requirements_revision === revision &&
    !!event.planning &&
    typeof event.attempt_revision === "number" &&
    typeof event.section_version === "number" &&
    (event.attempt_revision > cursor.attempt_revision ||
      (event.attempt_revision === cursor.attempt_revision &&
        event.section_version >= cursor.section_version))
  );
}

function matches(
  detail: PlanDetail,
  sessionId: string,
  revision: number,
  approved: number | null,
  mismatch: boolean,
) {
  return (
    !mismatch &&
    detail.session_id === sessionId &&
    detail.requirements_revision === revision &&
    approved === revision
  );
}

export function canApprovePlan(
  detail: PlanDetail | null,
  sessionId: string,
  revision: number,
  approved: number | null,
  mismatch: boolean,
): boolean {
  if (
    !detail ||
    !matches(detail, sessionId, revision, approved, mismatch) ||
    detail.partial ||
    !detail.plan
  )
    return false;
  const active = detail.planning.active;
  return (
    ["review_ready", "approved"].includes(detail.planning.status) &&
    !!active &&
    active.plan_id === detail.plan.id &&
    active.revision === detail.plan.revision &&
    active.requirements_revision === revision &&
    active.content_hash === detail.plan.content_hash
  );
}

export function canExportPlan(
  detail: PlanDetail | null,
  sessionId: string,
  revision: number,
  approved: number | null,
  mismatch: boolean,
): boolean {
  if (
    !canApprovePlan(detail, sessionId, revision, approved, mismatch) ||
    !detail
  )
    return false;
  const { active, approval, status } = detail.planning;
  return (
    status === "approved" &&
    !!active &&
    !!approval &&
    active.plan_id === approval.plan_id &&
    active.revision === approval.revision &&
    active.content_hash === approval.content_hash &&
    active.requirements_revision === approval.requirements_revision
  );
}

export function canGeneratePlan(
  detail: PlanDetail | null,
  ready: boolean,
  revision: number,
  approved: number | null,
  mismatch: boolean,
): boolean {
  if (!ready || mismatch || approved !== revision) return false;
  if (!detail) return true;
  return (
    detail.planning.status !== "planning" &&
    (detail.planning.attempts.length < detail.attempt_limit ||
      ["review_ready", "approved"].includes(detail.planning.status))
  );
}

export function draftViews(
  attempt: PlanAttempt,
): { human: string; engineering: string } | null {
  const outline = attempt.outline;
  if (!outline) return null;
  const citation = (claim: PlanStatement) =>
    `(${claim.status}) ${claim.text} [${claim.ledger_ids.join(", ")}]`;
  const heading = `DRAFT - not approved | ${attempt.plan_id} | revision ${attempt.revision}\n`;
  const human = [
    heading,
    citation(outline.vision),
    "\nUser journeys",
    ...outline.journeys.map(citation),
    "\nSpecification",
    ...outline.specification.map(citation),
    "\nConstraints",
    ...outline.common_rules.map(citation),
    "\nProposed choices and unresolved questions",
    ...outline.choices.map(citation),
    "\nWireframes",
    ...attempt.screens.flatMap((s) => [
      s.ref,
      citation(s.purpose),
      ...Object.entries(s.wireframes).flat(),
    ]),
  ].join("\n");
  const engineering = [
    heading,
    outline.architecture,
    "\nPhases",
    ...outline.phases.map(
      (p) =>
        `${p.ref}: ${p.title} <- ${p.depends_on.join(", ") || "approved requirements"}\n` +
        (attempt.phases.find((x) => x.ref === p.ref)
          ? "Section accepted; final verification pending"
          : "Details pending"),
    ),
    ...attempt.phases.flatMap((p) => [
      p.id,
      citation(p.goal),
      p.flow,
      JSON.stringify(p.packages, null, 2),
    ]),
  ].join("\n");
  return { human, engineering };
}
