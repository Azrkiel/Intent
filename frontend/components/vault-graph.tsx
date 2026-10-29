"use client";

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
} from "react";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationNodeDatum,
} from "d3-force";
import {
  Crosshair,
  Minus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Settings2,
} from "lucide-react";
import {
  zoomAt,
  type Camera,
  type GraphEdge,
  type GraphNode,
  type NoteKind,
} from "@/lib/vault";

const colors: Record<NoteKind, string> = {
  plan: "#bce3b4",
  phase: "#a8b8ef",
  package: "#edbb91",
  task: "#93b9c1",
  spec: "#c8b2d9",
  screen: "#9bcdb3",
  note: "#b1bab5",
};
interface PointNode extends SimulationNodeDatum {
  id: string;
}
type Gesture = {
  pointer: number;
  node?: PointNode;
  x: number;
  y: number;
  nx: number;
  ny: number;
  camera: Camera;
  moved: boolean;
};

export function VaultGraph({
  graph,
  selected,
  query,
  onSelect,
  storageKey,
}: {
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  selected: string;
  query: string;
  onSelect: (node: GraphNode) => void;
  storageKey: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const simulation = useRef<Simulation<PointNode, undefined> | null>(null);
  const positions = useRef(new Map<string, PointNode>());
  const gesture = useRef<Gesture | null>(null);
  const [size, setSize] = useState({ width: 700, height: 540 });
  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, scale: 1 });
  const [hovered, setHovered] = useState<string | null>(null);
  const [controls, setControls] = useState(false);
  const [labels, setLabels] = useState(true);
  const [arrows, setArrows] = useState(false);
  const [nodeSize, setNodeSize] = useState(1);
  const [distance, setDistance] = useState(115);
  const [repulsion, setRepulsion] = useState(240);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [hidden, setHidden] = useState<NoteKind[]>([]);
  const [reset, setReset] = useState(0);
  const [, render] = useState(0);
  const arrowId = useId().replace(/:/g, "");
  const visible = useMemo(
    () =>
      graph.nodes.filter(
        (n) =>
          n.id === "plan" ||
          (!hidden.includes(n.kind) &&
            (!query ||
              `${n.title} ${n.path}`
                .toLowerCase()
                .includes(query.toLowerCase()))),
      ),
    [graph.nodes, query, hidden],
  );
  const visibleIds = new Set(visible.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
  );
  const topology = JSON.stringify([visible.map((n) => n.id), edges]);
  const active = hovered || selected;
  const neighbors = new Set([
    active,
    ...edges.flatMap((e) =>
      e.source === active ? [e.target] : e.target === active ? [e.source] : [],
    ),
  ]);
  const degree = new Map<string, number>();
  edges.forEach((e) => {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  });

  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setSize({ width, height });
    });
    if (container.current) observer.observe(container.current);
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) || "{}");
      Object.entries(stored)
        .slice(0, 500)
        .forEach(([id, value]) => {
          const point = value as { x: number; y: number };
          if (Number.isFinite(point.x) && Number.isFinite(point.y))
            positions.current.set(id, { id, x: point.x, y: point.y });
        });
    } catch {
      /* Layout is optional; note content is saved by the API. */
    }
    return () => {
      observer.disconnect();
      media.removeEventListener("change", update);
    };
  }, [storageKey]);

  function remember() {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify(
          Object.fromEntries(
            [...positions.current].map(([id, n]) => [id, { x: n.x, y: n.y }]),
          ),
        ),
      );
    } catch {
      /* Optional layout storage. */
    }
  }

  useEffect(() => {
    const nodes = visible.map((node, index) => {
      const previous = positions.current.get(node.id);
      const angle = index * 2.399963;
      const radius = node.id === "plan" ? 0 : Math.sqrt(index + 1) * 65;
      const point = previous ?? {
        id: node.id,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      };
      positions.current.set(node.id, point);
      return point;
    });
    const sim = forceSimulation(nodes)
      .force(
        "link",
        forceLink<PointNode, { source: string; target: string }>(
          edges.map((e) => ({ ...e })),
        )
          .id((n) => n.id)
          .distance(distance)
          .strength(0.25),
      )
      .force("charge", forceManyBody<PointNode>().strength(-repulsion))
      .force("collide", forceCollide<PointNode>(30))
      .force(
        "x",
        forceX<PointNode>(0).strength((n) => (n.id === "plan" ? 0.5 : 0.025)),
      )
      .force(
        "y",
        forceY<PointNode>(0).strength((n) => (n.id === "plan" ? 0.5 : 0.025)),
      );
    simulation.current = sim;
    sim.on("tick", () => render((frame) => frame + 1));
    sim.on("end", remember);
    if (reduced) {
      sim.stop();
      sim.tick(180);
    }
    if (paused) sim.stop();
    render((frame) => frame + 1);
    return () => {
      sim.stop();
      remember();
    };
    // Only topology and force settings restart physics; editing prose retains positions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topology, distance, repulsion, paused, reduced, reset]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      if ((event.target as Element).closest(".vault-graph-settings")) return;
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      setCamera((current) =>
        zoomAt(
          current,
          {
            x: event.clientX - rect.left - rect.width / 2,
            y: event.clientY - rect.top - rect.height / 2,
          },
          Math.exp(-event.deltaY * 0.0015),
        ),
      );
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);

  function fit() {
    const points = visible
      .map((n) => positions.current.get(n.id))
      .filter((n): n is PointNode => !!n);
    if (!points.length) return;
    const xs = points.map((n) => n.x ?? 0),
      ys = points.map((n) => n.y ?? 0);
    const minX = Math.min(...xs) - 70,
      maxX = Math.max(...xs) + 70;
    const minY = Math.min(...ys) - 60,
      maxY = Math.max(...ys) + 60;
    const scale = Math.min(
      1.5,
      Math.max(
        0.15,
        Math.min(size.width / (maxX - minX), size.height / (maxY - minY)) *
          0.85,
      ),
    );
    setCamera({
      scale,
      x: (-(minX + maxX) / 2) * scale,
      y: (-(minY + maxY) / 2) * scale,
    });
  }
  function pointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || gesture.current) return;
    const id = (event.target as Element)
      .closest("[data-node-id]")
      ?.getAttribute("data-node-id");
    const node = id ? positions.current.get(id) : undefined;
    gesture.current = {
      pointer: event.pointerId,
      node,
      x: event.clientX,
      y: event.clientY,
      nx: node?.x ?? 0,
      ny: node?.y ?? 0,
      camera,
      moved: false,
    };
    svg.current?.setPointerCapture(event.pointerId);
    if (node) {
      node.fx = node.x;
      node.fy = node.y;
      if (!reduced && !paused) simulation.current?.alphaTarget(0.15).restart();
    }
  }
  function pointerMove(event: PointerEvent<SVGSVGElement>) {
    const g = gesture.current;
    if (!g || event.pointerId !== g.pointer) return;
    const dx = event.clientX - g.x,
      dy = event.clientY - g.y;
    if (Math.hypot(dx, dy) > 4) g.moved = true;
    if (g.node) {
      g.node.x = g.node.fx = g.nx + dx / g.camera.scale;
      g.node.y = g.node.fy = g.ny + dy / g.camera.scale;
      render((frame) => frame + 1);
    } else setCamera({ ...g.camera, x: g.camera.x + dx, y: g.camera.y + dy });
  }
  function release(event: PointerEvent<SVGSVGElement>, cancelled = false) {
    const g = gesture.current;
    if (!g || event.pointerId !== g.pointer) return;
    if (g.node) {
      g.node.fx = null;
      g.node.fy = null;
      simulation.current?.alphaTarget(0);
      if (!g.moved && !cancelled) {
        const node = graph.nodes.find((n) => n.id === g.node!.id);
        if (node) onSelect(node);
      }
      remember();
    }
    gesture.current = null;
    if (svg.current?.hasPointerCapture(event.pointerId))
      svg.current.releasePointerCapture(event.pointerId);
  }

  return (
    <div
      ref={container}
      className="vault-graph"
      aria-label="Markdown note graph"
    >
      <div className="vault-graph-caption">
        <span className="vault-live-dot" />
        {visible.filter((n) => !n.missing).length} notes<span>·</span>
        {edges.length} links
      </div>
      <button
        className="vault-icon-button vault-settings-button"
        aria-label="Graph settings"
        aria-expanded={controls}
        onClick={() => setControls(!controls)}
      >
        <Settings2 size={16} />
      </button>
      {controls && (
        <div className="vault-graph-settings">
          <div className="vault-settings-title">
            Graph settings
            <button
              className="vault-text-button"
              onClick={() => {
                setHidden([]);
                setLabels(true);
                setArrows(false);
                setNodeSize(1);
                setDistance(115);
                setRepulsion(240);
              }}
            >
              Defaults
            </button>
          </div>
          <fieldset>
            <legend>Show notes</legend>
            {(Object.keys(colors) as NoteKind[])
              .filter((k) => k !== "plan")
              .map((kind) => (
                <label key={kind}>
                  <span style={{ color: colors[kind] }}>{kind}</span>
                  <input
                    type="checkbox"
                    checked={!hidden.includes(kind)}
                    onChange={() =>
                      setHidden((current) =>
                        current.includes(kind)
                          ? current.filter((k) => k !== kind)
                          : [...current, kind],
                      )
                    }
                  />
                </label>
              ))}
          </fieldset>
          <fieldset>
            <legend>Display</legend>
            <label>
              Labels
              <input
                type="checkbox"
                checked={labels}
                onChange={(e) => setLabels(e.target.checked)}
              />
            </label>
            <label>
              Arrows
              <input
                type="checkbox"
                checked={arrows}
                onChange={(e) => setArrows(e.target.checked)}
              />
            </label>
            <label>
              Node size
              <input
                aria-label="Node size"
                type="range"
                min="0.6"
                max="2"
                step="0.1"
                value={nodeSize}
                onChange={(e) => setNodeSize(Number(e.target.value))}
              />
            </label>
          </fieldset>
          <fieldset>
            <legend>Forces</legend>
            <label>
              Link distance
              <input
                aria-label="Link distance"
                type="range"
                min="45"
                max="240"
                value={distance}
                onChange={(e) => setDistance(Number(e.target.value))}
              />
            </label>
            <label>
              Repulsion
              <input
                aria-label="Repulsion"
                type="range"
                min="30"
                max="700"
                value={repulsion}
                onChange={(e) => setRepulsion(Number(e.target.value))}
              />
            </label>
          </fieldset>
          {reduced && (
            <p>Reduced motion is on. Layout settles without animation.</p>
          )}
        </div>
      )}
      <svg
        ref={svg}
        viewBox={`0 0 ${size.width} ${size.height}`}
        role="group"
        aria-label="Interactive graph. Drag nodes or the background. Use arrow keys to pan, plus and minus to zoom, Home to fit."
        tabIndex={0}
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={(e) => release(e)}
        onPointerCancel={(e) => release(e, true)}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          const step = event.shiftKey ? 100 : 35;
          if (
            ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
              event.key,
            )
          ) {
            event.preventDefault();
            setCamera((c) => ({
              ...c,
              x:
                c.x +
                (event.key === "ArrowLeft"
                  ? step
                  : event.key === "ArrowRight"
                    ? -step
                    : 0),
              y:
                c.y +
                (event.key === "ArrowUp"
                  ? step
                  : event.key === "ArrowDown"
                    ? -step
                    : 0),
            }));
          }
          if (["+", "=", "-"].includes(event.key)) {
            event.preventDefault();
            setCamera((c) =>
              zoomAt(c, { x: 0, y: 0 }, event.key === "-" ? 0.8 : 1.25),
            );
          }
          if (event.key === "Home") {
            event.preventDefault();
            fit();
          }
        }}
      >
        <defs>
          <marker
            id={arrowId}
            viewBox="0 0 10 10"
            refX="20"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#8d9c91" />
          </marker>
        </defs>
        <g
          data-graph-camera
          transform={`translate(${size.width / 2 + camera.x},${size.height / 2 + camera.y}) scale(${camera.scale})`}
        >
          {edges.map((edge) => {
            const a = positions.current.get(edge.source),
              b = positions.current.get(edge.target);
            if (!a || !b) return null;
            const lit = edge.source === active || edge.target === active;
            return (
              <line
                key={`${edge.source}:${edge.target}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={lit ? "#b8ccad" : "#657168"}
                opacity={active ? (lit ? 0.6 : 0.13) : 0.35}
                strokeWidth={lit ? 1.3 : 0.8}
                markerEnd={arrows ? `url(#${arrowId})` : undefined}
              />
            );
          })}
          {visible.map((node) => {
            const point = positions.current.get(node.id);
            if (!point) return null;
            const radius =
              (node.id === "plan"
                ? 12
                : 4.5 + Math.min(5, (degree.get(node.id) ?? 0) * 0.6)) *
              nodeSize;
            const lit = !active || neighbors.has(node.id);
            return (
              <g
                key={node.id}
                data-node-id={node.id}
                data-note-path={node.path}
                transform={`translate(${point.x ?? 0},${point.y ?? 0})`}
                className={`vault-node ${selected === node.id ? "is-selected" : ""}`}
                role="button"
                tabIndex={0}
                aria-label={`${node.title}${node.missing ? ", missing note" : ""}`}
                aria-pressed={selected === node.id}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(node.id)}
                onBlur={() => setHovered(null)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(node);
                  }
                }}
              >
                <title>
                  {node.path}
                  {node.missing ? " — create this note" : ""}
                </title>
                <circle
                  className="vault-node-hit"
                  r={Math.max(20, radius + 7)}
                  fill="transparent"
                />
                {selected === node.id && (
                  <circle
                    r={radius + 6}
                    fill="none"
                    stroke={colors[node.kind]}
                    strokeWidth="1"
                    opacity="0.35"
                  />
                )}
                <circle
                  r={radius}
                  fill={node.missing ? "#222824" : colors[node.kind]}
                  stroke={colors[node.kind]}
                  strokeWidth={node.missing ? 1.4 : 0.5}
                  strokeDasharray={node.missing ? "2 2" : undefined}
                  opacity={lit ? 1 : 0.2}
                />
                {(labels || hovered === node.id || selected === node.id) && (
                  <text
                    textAnchor="middle"
                    y={radius + 18}
                    fill={lit ? "#e1e8df" : "#727e74"}
                    opacity={lit ? 1 : 0.4}
                    fontSize={node.id === "plan" ? 12 : 10.5}
                    fontWeight={node.id === "plan" ? 600 : 400}
                  >
                    {node.title.length > 36
                      ? node.title.slice(0, 34) + "…"
                      : node.title}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      <div className="vault-graph-bottom">
        <span>
          Drag to explore<span className="vault-hint-divider">/</span>Scroll to
          zoom
        </span>
        <div>
          <button
            className="vault-icon-button"
            aria-label={paused ? "Resume graph motion" : "Pause graph motion"}
            aria-pressed={paused}
            onClick={() => setPaused(!paused)}
          >
            {paused ? <Play size={15} /> : <Pause size={15} />}
          </button>
          <button
            className="vault-icon-button"
            aria-label="Reset graph layout"
            onClick={() => {
              positions.current.clear();
              setReset((n) => n + 1);
              setCamera({ x: 0, y: 0, scale: 1 });
            }}
          >
            <RotateCcw size={15} />
          </button>
          <button
            className="vault-icon-button"
            aria-label="Fit graph"
            onClick={fit}
          >
            <Crosshair size={16} />
          </button>
          <button
            className="vault-icon-button"
            aria-label="Zoom out"
            onClick={() => setCamera((c) => zoomAt(c, { x: 0, y: 0 }, 0.8))}
          >
            <Minus size={16} />
          </button>
          <span className="vault-zoom-label">
            {Math.round(camera.scale * 100)}%
          </span>
          <button
            className="vault-icon-button"
            aria-label="Zoom in"
            onClick={() => setCamera((c) => zoomAt(c, { x: 0, y: 0 }, 1.25))}
          >
            <Plus size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
