import { describe, expect, it } from "vitest";
import {
  graphBreadcrumbs,
  graphKey,
  graphSelection,
  graphVisibility,
  isCurrentGraph,
  radialLayout,
  rootCamera,
  type PlanGraphData,
} from "./plan-graph";

it("centers the initial root at a readable scale for the available canvas", () => {
  expect(rootCamera(550, 360)).toEqual({ x: 0, y: 0, width: 880, height: 576 });
  const mobile = rootCamera(240, 300);
  expect(mobile.x).toBe(0);
  expect(mobile.y).toBe(0);
  expect(mobile.width).toBe(384);
  expect((240 * 200) / mobile.width).toBeGreaterThanOrEqual(100);
});

const graph: PlanGraphData = {
  graph_schema_version: "plan-graph-v1",
  source: {
    plan_id: "plan",
    revision: 1,
    requirements_revision: 3,
    content_hash: "a".repeat(64),
    mode: "demo",
  },
  state: "review_ready",
  partial: false,
  root_id: "root",
  nodes: [
    {
      id: "root",
      kind: "root",
      parent_id: null,
      title: "Project intent",
      status: "validated",
      body: { intent: "Build a counter" },
      source_paths: ["/outline"],
      citations: ["L1"],
    },
    {
      id: "P1",
      kind: "phase",
      parent_id: "root",
      title: "First phase",
      status: "validated",
      body: {},
      source_paths: [],
      citations: [],
    },
    {
      id: "P1-W1",
      kind: "package",
      parent_id: "P1",
      title: "Counter",
      status: "validated",
      body: { handoff: { outputs: ["hidden Unicode 保存"] } },
      source_paths: [],
      citations: [],
    },
    {
      id: "P1-W1-T1",
      kind: "task",
      parent_id: "P1-W1",
      title: "Write counter",
      status: "validated",
      body: { checks: [{ command: ["git", "diff", "--check"] }] },
      source_paths: [],
      citations: [],
    },
    {
      id: "P2",
      kind: "phase",
      parent_id: "root",
      title: "Next phase",
      status: "pending",
      body: {},
      source_paths: [],
      citations: [],
    },
  ],
  edges: [
    {
      id: "e1",
      source: "root",
      target: "P1",
      type: "contains",
      provenance: "Plan hierarchy",
    },
    {
      id: "e2",
      source: "P1",
      target: "P1-W1",
      type: "contains",
      provenance: "Plan hierarchy",
    },
    {
      id: "e3",
      source: "P1-W1",
      target: "P1-W1-T1",
      type: "contains",
      provenance: "Plan hierarchy",
    },
    {
      id: "e4",
      source: "root",
      target: "P2",
      type: "contains",
      provenance: "Plan hierarchy",
    },
    {
      id: "e5",
      source: "P2",
      target: "P1",
      type: "depends_on",
      provenance: "Outline dependency",
    },
  ],
  source_fields: {},
};

describe("plan graph projection controls", () => {
  it("anchors the root at the origin with stable coordinates independent of selection or input order", () => {
    const positions = radialLayout(graph);
    expect(positions.root).toEqual({ x: 0, y: 0 });
    expect(
      radialLayout({ ...graph, nodes: [...graph.nodes].reverse() }),
    ).toEqual(positions);
    expect(
      new Set(Object.values(positions).map((p) => `${p.x},${p.y}`)).size,
    ).toBe(graph.nodes.length);
  });
  it("keeps canonical selection and ancestry independent of cross links", () => {
    expect(graphSelection(graph, "unknown").id).toBe("root");
    expect(graphBreadcrumbs(graph, "P1-W1-T1").map((n) => n.id)).toEqual([
      "root",
      "P1",
      "P1-W1",
      "P1-W1-T1",
    ]);
    expect(graphBreadcrumbs(graph, "P2").map((n) => n.id)).toEqual([
      "root",
      "P2",
    ]);
  });
  it("searches all nested fields and restores the complete ancestor path through collapsed branches", () => {
    const result = graphVisibility(graph, {
      query: "保存",
      collapsed: new Set(["P1"]),
      kind: "all",
      status: "all",
    });
    expect(result.matchIds).toEqual(["P1-W1"]);
    expect(result.nodes.map((n) => n.id)).toEqual(["root", "P1", "P1-W1"]);
    expect(graphVisibility(graph, { query: "--check" }).matchIds).toEqual([
      "P1-W1-T1",
    ]);
  });
  it("counts collapsed and filtered nodes while preserving the underlying graph", () => {
    const result = graphVisibility(graph, { collapsed: new Set(["P1"]) });
    expect(result.nodes.map((n) => n.id)).toEqual(["root", "P1", "P2"]);
    expect(result.hiddenCount).toBe(2);
    expect(result.descendantCounts.P1).toBe(2);
    expect(
      graphVisibility(graph, { status: "pending" }).nodes.map((n) => n.id),
    ).toEqual(["root", "P2"]);
    expect(graph.nodes.length).toBe(5);
  });
  it("binds graph state to the exact source and refuses stale/partial approval identities", () => {
    const identity = {
      plan_id: "plan",
      revision: 1,
      requirements_revision: 3,
      content_hash: "a".repeat(64),
    };
    expect(isCurrentGraph(graph, 3, identity)).toBe(true);
    expect(isCurrentGraph({ ...graph, partial: true }, 3, identity)).toBe(
      false,
    );
    expect(isCurrentGraph({ ...graph, state: "blocked" }, 3, identity)).toBe(
      false,
    );
    expect(isCurrentGraph(graph, 4, identity)).toBe(false);
    expect(
      isCurrentGraph(graph, 3, { ...identity, content_hash: "b".repeat(64) }),
    ).toBe(false);
    expect(graphKey(graph)).not.toBe(
      graphKey({ ...graph, source: { ...graph.source, revision: 2 } }),
    );
  });
});
