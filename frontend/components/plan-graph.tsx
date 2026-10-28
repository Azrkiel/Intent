"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Crosshair,
  Maximize2,
  Minus,
  Plus,
  Search,
} from "lucide-react";
import {
  graphBreadcrumbs,
  graphSelection,
  graphVisibility,
  radialLayout,
  rootCamera,
  type GraphKind,
  type PlanGraphData,
} from "@/lib/plan-graph";

const kindNames: Record<GraphKind, string> = {
  root: "Project",
  phase: "Phase",
  package: "Subproject",
  task: "Task",
  screen: "Screen",
};
const readable = (key: string) => key.replaceAll("_", " ");

function BodyValue({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <p className="graph-pending">Details pending</p>;
  if (typeof value !== "object")
    return <p className="graph-value">{String(value)}</p>;
  if (Array.isArray(value))
    return value.length ? (
      <ol className="graph-values">
        {value.map((item, index) => (
          <li key={index}>
            <BodyValue value={item} />
          </li>
        ))}
      </ol>
    ) : (
      <p className="graph-empty-value">None declared</p>
    );
  const record = value as Record<string, unknown>;
  if (typeof record.text === "string" && Array.isArray(record.ledger_ids))
    return (
      <div className="graph-statement">
        <span className="graph-claim-status">{String(record.status)}</span>
        <p>{record.text}</p>
        <small>Citations: {record.ledger_ids.map(String).join(", ")}</small>
      </div>
    );
  return (
    <dl className="graph-fields">
      {Object.entries(record).map(([key, item]) => (
        <div key={key}>
          <dt>{readable(key)}</dt>
          <dd>
            <BodyValue value={item} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function PlanGraph({
  graph,
  stale = false,
}: {
  graph: PlanGraphData;
  stale?: boolean;
}) {
  const [selectedId, setSelectedId] = useState(graph.root_id);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<GraphKind | "all">("all");
  const [status, setStatus] = useState<"all" | "validated" | "pending">("all");
  const [collapsed, setCollapsed] = useState(new Set<string>());
  const [camera, setCamera] = useState(rootCamera(550, 360));
  const canvas = useRef<SVGSVGElement>(null);
  const viewport = useRef({ width: 550, height: 360 });
  useEffect(() => {
    if (!canvas.current) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width <= 0 || height <= 0) return;
      viewport.current = { width, height };
      setCamera(rootCamera(width, height));
    });
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, []);
  const dragging = useRef<{
    x: number;
    y: number;
    cameraX: number;
    cameraY: number;
  } | null>(null);
  const positions = useMemo(() => radialLayout(graph), [graph]);
  const visible = graphVisibility(graph, { query, kind, status, collapsed });
  const selected = graphSelection(graph, selectedId);
  const breadcrumbs = graphBreadcrumbs(graph, selected.id);
  const links = graph.edges.filter(
    (edge) => edge.source === selected.id || edge.target === selected.id,
  );
  const searching = !!query.trim() || kind !== "all" || status !== "all";

  function toggle(id: string) {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function zoom(factor: number) {
    setCamera((previous) => {
      const width = Math.max(240, Math.min(4000, previous.width * factor));
      return {
        ...previous,
        width,
        height: (previous.height * width) / previous.width,
      };
    });
  }
  function fit() {
    const points = visible.nodes
      .map((node) => positions[node.id])
      .filter(Boolean);
    const left = Math.min(...points.map((point) => point.x)) - 150;
    const right = Math.max(...points.map((point) => point.x)) + 150;
    const top = Math.min(...points.map((point) => point.y)) - 100;
    const bottom = Math.max(...points.map((point) => point.y)) + 100;
    const width = Math.max(700, right - left, (bottom - top) * 1.36);
    setCamera({
      x: (left + right) / 2,
      y: (top + bottom) / 2,
      width,
      height: width / 1.36,
    });
  }
  function choose(id: string) {
    setSelectedId(id);
    setCollapsed((previous) => {
      const next = new Set(previous);
      graphBreadcrumbs(graph, id)
        .slice(0, -1)
        .forEach((node) => next.delete(node.id));
      return next;
    });
  }

  return (
    <section className="plan-graph" aria-label="Complete project graph">
      <div className="graph-identity">
        <strong>
          {graph.source.mode === "demo" ? "DEMO · synthetic plan" : "Live plan"}{" "}
          · {readable(graph.state)}
        </strong>
        <span>
          {graph.source.plan_id} · plan revision {graph.source.revision} ·
          requirements {graph.source.requirements_revision}
        </span>
        <code>SHA-256 {graph.source.content_hash}</code>
      </div>
      {(graph.partial ||
        stale ||
        graph.state === "stale" ||
        graph.state === "blocked") && (
        <p className="plan-notice">
          {stale || graph.state === "stale"
            ? "Stale plan · retained for inspection. Review current requirements before approval."
            : graph.partial
              ? "Partial plan · accepted sections only. Pending nodes have no implementation details."
              : "Blocked plan · inspect preserved sections and blocking reasons."}
        </p>
      )}
      <div className="graph-toolbar">
        <label className="graph-search">
          <Search size={15} />
          <span className="sr-only">Search every plan field</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search scope, handoffs, sources…"
          />
        </label>
        <label>
          <span className="sr-only">Filter node type</span>
          <select
            aria-label="Filter node type"
            value={kind}
            onChange={(event) =>
              setKind(event.target.value as GraphKind | "all")
            }
          >
            <option value="all">All types</option>
            {Object.entries(kindNames).map(([value, name]) => (
              <option key={value} value={value}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter detail status</span>
          <select
            aria-label="Filter detail status"
            value={status}
            onChange={(event) => setStatus(event.target.value as typeof status)}
          >
            <option value="all">All details</option>
            <option value="validated">Validated sections</option>
            <option value="pending">Pending details</option>
          </select>
        </label>
      </div>
      <div className="graph-workspace">
        <div className="graph-navigation">
          <div
            className="graph-canvas-controls"
            role="group"
            aria-label="Graph viewport controls"
          >
            <button
              title="Zoom in"
              aria-label="Zoom in"
              onClick={() => zoom(0.8)}
            >
              <Plus size={15} />
            </button>
            <button
              title="Zoom out"
              aria-label="Zoom out"
              onClick={() => zoom(1.25)}
            >
              <Minus size={15} />
            </button>
            <button
              onClick={() =>
                setCamera(
                  rootCamera(viewport.current.width, viewport.current.height),
                )
              }
            >
              <Crosshair size={14} /> Center root
            </button>
            <button onClick={fit}>
              <Maximize2 size={14} /> Fit
            </button>
          </div>
          <svg
            ref={canvas}
            className="graph-canvas"
            viewBox={`${camera.x - camera.width / 2} ${camera.y - camera.height / 2} ${camera.width} ${camera.height}`}
            aria-label="Project graph canvas. Drag the background or use arrow keys to pan; plus and minus keys zoom."
            role="group"
            tabIndex={0}
            onPointerDown={(event) => {
              if (event.target !== event.currentTarget) return;
              dragging.current = {
                x: event.clientX,
                y: event.clientY,
                cameraX: camera.x,
                cameraY: camera.y,
              };
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (!dragging.current) return;
              const bounds = event.currentTarget.getBoundingClientRect();
              const origin = dragging.current;
              setCamera((previous) => ({
                ...previous,
                x:
                  origin.cameraX -
                  ((event.clientX - origin.x) * previous.width) / bounds.width,
                y:
                  origin.cameraY -
                  ((event.clientY - origin.y) * previous.height) /
                    bounds.height,
              }));
            }}
            onPointerUp={() => {
              dragging.current = null;
            }}
            onPointerCancel={() => {
              dragging.current = null;
            }}
            onKeyDown={(event) => {
              if (event.target !== event.currentTarget) return;
              const steps: Record<string, [number, number]> = {
                ArrowLeft: [-60, 0],
                ArrowRight: [60, 0],
                ArrowUp: [0, -60],
                ArrowDown: [0, 60],
              };
              const step = steps[event.key];
              if (step) {
                event.preventDefault();
                setCamera((previous) => ({
                  ...previous,
                  x: previous.x + step[0],
                  y: previous.y + step[1],
                }));
              } else if (["+", "=", "-"].includes(event.key)) {
                event.preventDefault();
                zoom(event.key === "-" ? 1.25 : 0.8);
              }
            }}
          >
            <title>Project plan, centered on its root</title>
            {visible.edges.map((edge) => {
              const from = positions[edge.source],
                to = positions[edge.target];
              if (!from || !to) return null;
              return (
                <g key={edge.id} className={`graph-edge ${edge.type}`}>
                  <title>
                    {edge.source} {readable(edge.type)} {edge.target}:{" "}
                    {edge.provenance}
                  </title>
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  {edge.type === "depends_on" && (
                    <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8}>
                      depends on
                    </text>
                  )}
                </g>
              );
            })}
            {visible.nodes.map((node) => {
              const position = positions[node.id];
              if (!position) return null;
              const root = node.kind === "root";
              const task = node.kind === "task";
              const width = root
                ? 200
                : task
                  ? 50
                  : node.kind === "package"
                    ? 130
                    : 164;
              const titleLimit = root ? 23 : node.kind === "package" ? 16 : 20;
              return (
                <g
                  key={node.id}
                  transform={`translate(${position.x},${position.y})`}
                  className={`graph-node ${node.kind} ${node.status} ${selected.id === node.id ? "selected" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${kindNames[node.kind]} ${node.id}: ${node.title}${node.status === "pending" ? ", details pending" : ""}`}
                  aria-pressed={selected.id === node.id}
                  onClick={() => choose(node.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      choose(node.id);
                    }
                  }}
                >
                  <title>{node.title}</title>
                  <rect
                    x={-width / 2}
                    y={root ? -43 : task ? -20 : -32}
                    width={width}
                    height={root ? 86 : task ? 40 : 64}
                    rx={root ? 42 : task ? 20 : 11}
                  />
                  <text
                    className="graph-node-type"
                    textAnchor="middle"
                    y={task ? 4 : -10}
                  >
                    {task
                      ? node.id.split("-").at(-1)
                      : root
                        ? "PROJECT ROOT"
                        : node.kind === "package"
                          ? node.id
                          : `${kindNames[node.kind].toUpperCase()} · ${node.id}`}
                  </text>
                  {!task && (
                    <text
                      className="graph-node-title"
                      textAnchor="middle"
                      y={12}
                    >
                      {node.title.length > titleLimit
                        ? node.title.slice(0, titleLimit - 2) + "…"
                        : node.title}
                    </text>
                  )}
                  {node.status === "pending" && (
                    <text
                      className="graph-node-pending"
                      textAnchor="middle"
                      y={25}
                    >
                      details pending
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
          <p className="graph-legend">
            Solid: contains · dashed: depends on · dotted: screen attachment
          </p>
          <div className="graph-outline-heading">
            <strong>Plan outline</strong>
            <span aria-live="polite">
              {visible.nodes.length}/{graph.nodes.length} nodes ·{" "}
              {visible.hiddenCount} hidden
            </span>
          </div>
          {searching && (
            <p className="graph-results" role="status">
              {visible.matchIds.length} matching node
              {visible.matchIds.length === 1 ? "" : "s"}. Ancestors remain
              visible.
            </p>
          )}
          <ol
            className="graph-outline"
            aria-label="Keyboard accessible plan outline"
          >
            {visible.nodes.map((node) => {
              const hasChildren = graph.nodes.some(
                (child) => child.parent_id === node.id,
              );
              const depth = graphBreadcrumbs(graph, node.id).length - 1;
              return (
                <li key={node.id} style={{ paddingLeft: `${depth * 14}px` }}>
                  {hasChildren ? (
                    <button
                      className="graph-collapse"
                      aria-label={`${collapsed.has(node.id) ? "Expand" : "Collapse"} ${node.id}`}
                      aria-expanded={!collapsed.has(node.id) || searching}
                      disabled={searching}
                      onClick={() => toggle(node.id)}
                    >
                      {collapsed.has(node.id) && !searching ? (
                        <ChevronRight size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                    </button>
                  ) : (
                    <span className="graph-collapse-spacer" />
                  )}
                  <button
                    className="graph-outline-node"
                    aria-pressed={selected.id === node.id}
                    onClick={() => choose(node.id)}
                  >
                    <small>
                      {node.id === graph.root_id ? "PROJECT" : node.id}
                    </small>
                    <span>{node.title}</span>
                    {node.status === "pending" && <em>Pending</em>}
                    {collapsed.has(node.id) && !searching && (
                      <em>{visible.descendantCounts[node.id] ?? 0} hidden</em>
                    )}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
        <article className="graph-inspector" aria-label="Selected node details">
          <nav className="graph-breadcrumbs" aria-label="Node ancestors">
            {breadcrumbs.map((node) => (
              <button
                key={node.id}
                onClick={() => choose(node.id)}
                aria-current={node.id === selected.id ? "location" : undefined}
              >
                {node.id === graph.root_id ? "Project root" : node.id}
              </button>
            ))}
          </nav>
          <div className="eyebrow">
            {kindNames[selected.kind]} ·{" "}
            {selected.status === "pending"
              ? "DETAILS PENDING"
              : "VALIDATED SECTION"}
          </div>
          <h4>{selected.title}</h4>
          <p className="graph-read-policy">
            {selected.kind === "root"
              ? "Overall intent, shared design, orchestration, and phase gates."
              : selected.kind === "package"
                ? "Assigned scope and planned handoff. A worker receives this subtree and its ancestors."
                : "Containment defines ancestry. Dependency links describe input obligations."}
          </p>
          <BodyValue value={selected.body} />
          <details className="graph-provenance">
            <summary>Source fields and exact node data</summary>
            <ul>
              {selected.source_paths.map((path) => (
                <li key={path}>
                  <code>{path}</code>
                </li>
              ))}
            </ul>
            <pre>{JSON.stringify(selected.body, null, 2)}</pre>
          </details>
          <details className="graph-links">
            <summary>Connections ({links.length})</summary>
            <ul>
              {links.map((edge) => (
                <li key={edge.id}>
                  <strong>
                    {edge.source} {readable(edge.type)} {edge.target}
                  </strong>
                  <p>{edge.provenance}</p>
                  <button
                    onClick={() =>
                      choose(
                        edge.source === selected.id ? edge.target : edge.source,
                      )
                    }
                  >
                    Inspect{" "}
                    {edge.source === selected.id ? edge.target : edge.source}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        </article>
      </div>
    </section>
  );
}
