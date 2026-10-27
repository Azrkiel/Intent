import { describe, expect, it } from "vitest";
import {
  canApprovePlan,
  canExportPlan,
  canGeneratePlan,
  acceptPlanEvent,
  type PlanDetail,
  type PlanningState,
} from "./planning";

const identity = {
  plan_id: "plan",
  revision: 1,
  requirements_revision: 3,
  content_hash: "a".repeat(64),
};
const state: PlanningState = {
  status: "review_ready",
  attempts: [],
  active: identity,
  approval: null,
};
const detail = {
  session_id: "session",
  requirements_revision: 3,
  planning: state,
  partial: false,
  plan: {
    id: "plan",
    revision: 1,
    requirements_revision: 3,
    content_hash: identity.content_hash,
  },
  attempt_limit: 2,
  execution_enabled: false,
} as PlanDetail;

describe("plan approval gates", () => {
  it("requires complete current matching content and requirements approval", () => {
    expect(canApprovePlan(detail, "session", 3, 3, false)).toBe(true);
    expect(canApprovePlan(detail, "other", 3, 3, false)).toBe(false);
    expect(canApprovePlan(detail, "session", 4, 3, false)).toBe(false);
    expect(
      canApprovePlan({ ...detail, partial: true }, "session", 3, 3, false),
    ).toBe(false);
    expect(canApprovePlan(detail, "session", 3, null, false)).toBe(false);
    expect(canApprovePlan(detail, "session", 3, 3, true)).toBe(false);
    expect(
      canApprovePlan(
        { ...detail, planning: { ...state, status: "blocked" } },
        "session",
        3,
        3,
        false,
      ),
    ).toBe(false);
  });
  it("exports only an explicitly approved matching hash", () => {
    expect(canExportPlan(detail, "session", 3, 3, false)).toBe(false);
    const approved = {
      ...detail,
      planning: { ...state, status: "approved" as const, approval: identity },
    };
    expect(canExportPlan(approved, "session", 3, 3, false)).toBe(true);
    expect(
      canExportPlan(
        { ...approved, plan: { ...approved.plan!, content_hash: "bad" } },
        "session",
        3,
        3,
        false,
      ),
    ).toBe(false);
  });
  it("enforces attempt allowance and mode guard", () => {
    expect(canGeneratePlan(detail, true, 3, 3, false)).toBe(true);
    expect(canGeneratePlan(detail, true, 3, 3, true)).toBe(false);
    expect(
      canGeneratePlan(
        {
          ...detail,
          planning: {
            ...state,
            status: "blocked",
            attempts: [{}, {}] as PlanningState["attempts"],
          },
        },
        true,
        3,
        3,
        false,
      ),
    ).toBe(false);
  });
});

describe("incremental plan events", () => {
  it("rejects stale sessions, revisions, attempts, and out-of-order sections", () => {
    const current = { attempt_revision: 2, section_version: 3 };
    const event = {
      session_id: "session",
      requirements_revision: 3,
      attempt_revision: 2,
      section_version: 4,
      planning: state,
    };
    expect(acceptPlanEvent(event, "session", 3, current)).toBe(true);
    expect(
      acceptPlanEvent({ ...event, session_id: "other" }, "session", 3, current),
    ).toBe(false);
    expect(acceptPlanEvent(event, "session", 4, current)).toBe(false);
    expect(
      acceptPlanEvent({ ...event, attempt_revision: 1 }, "session", 3, current),
    ).toBe(false);
    expect(
      acceptPlanEvent({ ...event, section_version: 1 }, "session", 3, current),
    ).toBe(false);
  });
  it("retains blocked error state as an accepted event", () => {
    expect(
      acceptPlanEvent(
        {
          session_id: "session",
          requirements_revision: 3,
          attempt_revision: 1,
          section_version: 1,
          planning: { ...state, status: "blocked" },
        },
        "session",
        3,
        { attempt_revision: 1, section_version: 1 },
      ),
    ).toBe(true);
  });
});
