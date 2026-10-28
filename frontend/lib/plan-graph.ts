import type { PlanIdentity } from "./planning";

export type GraphKind = "root" | "phase" | "package" | "task" | "screen";
export interface PlanGraphNode {
  id: string;
  kind: GraphKind;
  parent_id: string | null;
  title: string;
  status: "validated" | "pending";
  body: Record<string, unknown>;
  source_paths: string[];
  citations: string[];
}
export interface PlanGraphEdge {
  id: string;
  source: string;
  target: string;
  type: "contains" | "depends_on" | "attachment";
  provenance: string;
}
export interface PlanGraphData {
  graph_schema_version: "plan-graph-v1";
  source: PlanIdentity & { mode: "demo" | "live" };
  state: string;
  partial: boolean;
  root_id: string;
  nodes: PlanGraphNode[];
  edges: PlanGraphEdge[];
  source_fields: Record<string, { node_id: string; body_path: string }>;
}

export function graphKey(graph: PlanGraphData): string {
  return JSON.stringify(graph.source);
}

export function rootCamera(width: number, height: number) {
  return {
    x: 0,
    y: 0,
    width: Math.max(240, width * 1.6),
    height: Math.max(240, height * 1.6),
  };
}

export function graphSelection(
  graph: PlanGraphData,
  id: string,
): PlanGraphNode {
  const node =
    graph.nodes.find((n) => n.id === id) ??
    graph.nodes.find((n) => n.id === graph.root_id);
  if (!node) throw new Error("Plan graph has no project root");
  return node;
}

export function graphBreadcrumbs(
  graph: PlanGraphData,
  id: string,
): PlanGraphNode[] {
  const result: PlanGraphNode[] = [];
  const visited = new Set<string>();
  let node: PlanGraphNode | undefined = graphSelection(graph, id);
  while (node && !visited.has(node.id)) {
    visited.add(node.id);
    result.unshift(node);
    node = graph.nodes.find((n) => n.id === node!.parent_id);
  }
  return result;
}

export function isCurrentGraph(
  graph: PlanGraphData,
  revision: number,
  identity: PlanIdentity,
): boolean {
  return (
    !graph.partial &&
    ["approved", "review_ready"].includes(graph.state) &&
    graph.source.requirements_revision === revision &&
    graph.source.plan_id === identity.plan_id &&
    graph.source.revision === identity.revision &&
    graph.source.content_hash === identity.content_hash &&
    identity.requirements_revision === revision
  );
}

export function radialLayout(
  graph: PlanGraphData,
): Record<string, { x: number; y: number }> {
  const positions: Record<string, { x: number; y: number }> = {
    [graph.root_id]: { x: 0, y: 0 },
  };
  const children = (id: string) =>
    graph.nodes
      .filter((n) => n.parent_id === id)
      .sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
  function place(
    id: string,
    angle: number,
    span: number,
    depth: number,
    visited: Set<string>,
  ) {
    if (visited.has(id)) return;
    visited = new Set(visited).add(id);
    if (depth) {
      const radius = depth === 1 ? 200 : depth === 2 ? 390 : 560;
      positions[id] = {
        x: Math.round(Math.cos(angle) * radius),
        y: Math.round(Math.sin(angle) * radius),
      };
    }
    const nodes = children(id);
    nodes.forEach((node, index) => {
      const step = span / Math.max(nodes.length, 1);
      const next =
        nodes.length === 1 ? angle : angle - span / 2 + step * (index + 0.5);
      place(
        node.id,
        next,
        Math.min(step * 0.8, Math.PI / 2),
        depth + 1,
        visited,
      );
    });
  }
  const roots = children(graph.root_id);
  roots.forEach((node, index) =>
    place(
      node.id,
      -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(roots.length, 1),
      ((2 * Math.PI) / Math.max(roots.length, 1)) * 0.8,
      1,
      new Set([graph.root_id]),
    ),
  );
  return positions;
}

export function graphVisibility(
  graph: PlanGraphData,
  options: {
    query?: string;
    kind?: GraphKind | "all";
    status?: "validated" | "pending" | "all";
    collapsed?: Set<string>;
  } = {},
) {
  const query = (options.query ?? "").trim().toLocaleLowerCase();
  const filtering =
    !!query ||
    (!!options.kind && options.kind !== "all") ||
    (!!options.status && options.status !== "all");
  const matches = graph.nodes.filter(
    (node) =>
      (!query || JSON.stringify(node).toLocaleLowerCase().includes(query)) &&
      (!options.kind || options.kind === "all" || node.kind === options.kind) &&
      (!options.status ||
        options.status === "all" ||
        node.status === options.status),
  );
  const included = new Set<string>([graph.root_id]);
  if (filtering)
    matches.forEach((node) =>
      graphBreadcrumbs(graph, node.id).forEach((parent) =>
        included.add(parent.id),
      ),
    );
  else
    graph.nodes.forEach((node) => {
      const parents = graphBreadcrumbs(graph, node.id).slice(0, -1);
      if (!parents.some((parent) => options.collapsed?.has(parent.id)))
        included.add(node.id);
    });
  const nodes = graph.nodes.filter((node) => included.has(node.id));
  const descendantCounts: Record<string, number> = {};
  graph.nodes.forEach((node) => {
    graphBreadcrumbs(graph, node.id)
      .slice(0, -1)
      .forEach((parent) => {
        descendantCounts[parent.id] = (descendantCounts[parent.id] ?? 0) + 1;
      });
  });
  return {
    nodes,
    edges: graph.edges.filter(
      (edge) => included.has(edge.source) && included.has(edge.target),
    ),
    hiddenCount: graph.nodes.length - nodes.length,
    descendantCounts,
    matchIds: matches.map((node) => node.id),
  };
}
