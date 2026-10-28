import { describe, expect, it } from "vitest";
import {
  acceptsExecutionResponse,
  canReviewPhase,
  canStartPhase,
  canAnswerPermission,
  canRepairPhase,
  canApproveContext,
  canResumeContextPhase,
  type ExecutionContext,
  type ExecutionDetail,
  type ExecutionPhase,
  type ExecutionRun,
} from "./execution";

const plan = {
  plan_id: "plan",
  revision: 1,
  content_hash: "a".repeat(64),
  requirements_revision: 1,
};
const phase = {
  id: "phase",
  plan,
  phase_id: "P1",
  attempt: 1,
  status: "awaiting_phase_review",
  review_hash: "b".repeat(64),
  stale: false,
  promotion_intent: null,
  integration_intent: null,
} as ExecutionPhase;
const detail = {
  session_id: "session",
  requirements_revision: 1,
  plan,
  execution_enabled: true,
  phase_acceptance_enabled: true,
  simulation: false,
  phases: [phase],
  runs: [],
  reviews: [
    {
      evidence_hash: phase.review_hash,
      plan,
      phase_id: "P1",
      phase_execution_id: "phase",
      attempt: 1,
    },
  ],
  phase_options: [
    { id: "P1", can_start: false },
    { id: "P2", can_start: false },
  ],
} as unknown as ExecutionDetail;

describe("execution gates", () => {
  it("requires the exact current context and prevents approval after dispatch", () => {
    const context = {
      plan,
      package_id: "P1-W1",
      phase_attempt: 1,
      context_hash: "c".repeat(64),
      packet_hash: "d".repeat(64),
      approved: false,
      current: true,
    } as ExecutionContext;
    const preparing = {
      ...detail,
      phases: [{ ...phase, status: "awaiting_context_review" as const }],
    };
    expect(canApproveContext(preparing, context, true)).toBe(true);
    expect(
      canApproveContext(detail, { ...context, current: false }, true),
    ).toBe(false);
    expect(
      canApproveContext(detail, { ...context, approved: true }, true),
    ).toBe(false);
    expect(
      canApproveContext(detail, { ...context, packet_hash: "" }, true),
    ).toBe(false);
    expect(
      canApproveContext(
        detail,
        { ...context, plan: { ...plan, revision: 2 } },
        true,
      ),
    ).toBe(false);
    expect(
      canApproveContext(detail, { ...context, phase_attempt: 2 }, true),
    ).toBe(false);
    expect(
      canApproveContext(
        {
          ...detail,
          runs: [
            { plan, package_id: "P1-W1", phase_attempt: 1 } as ExecutionRun,
          ],
        },
        context,
        true,
      ),
    ).toBe(false);
    expect(canApproveContext(detail, context, false)).toBe(false);
  });
  it("resumes the same paused phase only with an approved eligible context", () => {
    const paused = { ...phase, status: "awaiting_context_review" as const };
    const ready = {
      ...detail,
      phases: [paused],
      phase_options: [
        {
          id: "P1",
          packages: [{ id: "P1-W1", can_prepare: true, context_ready: true }],
          can_start: false,
        },
      ],
    } as ExecutionDetail;
    expect(canResumeContextPhase(ready, paused, true)).toBe(true);
    const partiallyReviewed = structuredClone(ready);
    partiallyReviewed.phase_options[0].packages.push({
      id: "P1-W2",
      owned_paths: ["api"],
      can_prepare: true,
      context_ready: false,
    });
    expect(canResumeContextPhase(partiallyReviewed, paused, true)).toBe(false);
    partiallyReviewed.phase_options[0].packages[1].context_ready = true;
    expect(canResumeContextPhase(partiallyReviewed, paused, true)).toBe(true);
    expect(
      canResumeContextPhase({ ...ready, phase_options: [] }, paused, true),
    ).toBe(false);
    expect(canResumeContextPhase(ready, { ...paused, stale: true }, true)).toBe(
      false,
    );
    expect(
      canResumeContextPhase(ready, { ...paused, status: "blocked" }, true),
    ).toBe(false);
    expect(canResumeContextPhase(ready, paused, false)).toBe(false);
  });
  it("ignores responses from other sessions, plans, revisions, or older polls", () => {
    expect(acceptsExecutionResponse(detail, "session", plan, 2, 1)).toBe(true);
    expect(acceptsExecutionResponse(detail, "other", plan, 2, 1)).toBe(false);
    expect(
      acceptsExecutionResponse(
        detail,
        "session",
        { ...plan, revision: 2 },
        2,
        1,
      ),
    ).toBe(false);
    expect(acceptsExecutionResponse(detail, "session", plan, 1, 2)).toBe(false);
    expect(
      acceptsExecutionResponse(
        { ...detail, requirements_revision: 2 },
        "session",
        plan,
        2,
        1,
      ),
    ).toBe(false);
  });
  it("shows retained state after correction while keeping the new revision current", () => {
    expect(
      acceptsExecutionResponse(
        { ...detail, requirements_revision: 2 },
        "session",
        plan,
        2,
        1,
        2,
      ),
    ).toBe(true);
    expect(acceptsExecutionResponse(detail, "session", plan, 2, 1, 2)).toBe(
      false,
    );
  });
  it("completed turns never count as phase acceptance or enable successors", () => {
    expect(canStartPhase(detail, "P2", true)).toBe(false);
    expect(
      canStartPhase(
        {
          ...detail,
          phase_options: [
            {
              id: "P2",
              can_start: true,
              reason: "",
              packages: [],
              title: "Next",
            },
          ],
        },
        "P2",
        true,
      ),
    ).toBe(false);
    const accepted = { ...phase, status: "accepted" as const };
    expect(
      canStartPhase(
        {
          ...detail,
          phases: [accepted],
          phase_options: [
            {
              id: "P2",
              can_start: true,
              reason: "",
              packages: [],
              title: "Next",
            },
          ],
        },
        "P2",
        true,
      ),
    ).toBe(true);
    expect(canStartPhase(detail, "P1", false)).toBe(false);
  });
  it("requires the exact current review and blocks stale or uncertain evidence", () => {
    expect(canReviewPhase(detail, phase, true)).toBe(true);
    for (const change of [
      { stale: true },
      { status: "blocked" },
      { promotion_intent: "unknown" },
      { review_hash: "old" },
      { attempt: 2 },
    ]) {
      expect(
        canReviewPhase(detail, { ...phase, ...change } as ExecutionPhase, true),
      ).toBe(false);
    }
    expect(canReviewPhase(detail, phase, false)).toBe(false);
  });
  it("ties permissions to run, turn, generation and expiration", () => {
    const permission = {
      id: "request",
      generation: "connection",
      thread_id: "thread",
      turn_id: "turn",
      status: "pending",
      expires_at: 200,
    };
    const run = {
      status: "running",
      generation: "connection",
      thread_id: "thread",
      turn_id: "turn",
      stale: false,
      cancel_requested: false,
      approvals: [permission],
    } as ExecutionRun;
    expect(canAnswerPermission(run, permission, true, 100)).toBe(true);
    for (const change of [
      { generation: "old" },
      { turn_id: "old" },
      { status: "responding" },
      { expires_at: 99 },
    ]) {
      expect(
        canAnswerPermission(run, { ...permission, ...change }, true, 100),
      ).toBe(false);
    }
    expect(
      canAnswerPermission(
        { ...run, cancel_requested: true },
        permission,
        true,
        100,
      ),
    ).toBe(false);
    expect(canAnswerPermission(run, permission, false, 100)).toBe(false);
  });
  it("allows explicit repair only after known terminal outcomes", () => {
    const blocked = { ...phase, status: "blocked" as const };
    const run = {
      plan,
      package_id: "P1-W1",
      phase_attempt: 1,
      turn_id: "turn",
      thread_id: "thread",
      turn_status: "completed",
      status: "integrated",
    } as ExecutionRun;
    expect(canRepairPhase({ ...detail, runs: [run] }, blocked, true)).toBe(
      true,
    );
    expect(
      canRepairPhase(
        { ...detail, runs: [{ ...run, turn_status: "unknown" }] },
        blocked,
        true,
      ),
    ).toBe(false);
    expect(
      canRepairPhase(
        { ...detail, runs: [{ ...run, status: "running" }] },
        blocked,
        true,
      ),
    ).toBe(false);
    expect(
      canRepairPhase(
        detail,
        { ...blocked, promotion_intent: "uncertain" },
        true,
      ),
    ).toBe(false);
  });
});
