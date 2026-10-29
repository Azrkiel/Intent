import { fromMarkdown } from "mdast-util-from-markdown";
import type { PlanIdentity } from "./planning";

export type NoteKind =
  "plan" | "phase" | "package" | "task" | "spec" | "screen" | "note";
export interface VaultNote {
  id: string;
  path: string;
  body: string;
  kind: NoteKind;
}
export interface VaultDocument {
  revision: number;
  notes: VaultNote[];
  source: PlanIdentity | null;
  source_status: "draft" | "validated" | null;
  demo: boolean;
}
export interface GraphNode {
  id: string;
  path: string;
  title: string;
  kind: NoteKind;
  missing?: boolean;
}
export interface GraphEdge {
  source: string;
  target: string;
}
interface AstNode {
  type: string;
  value?: string;
  url?: string;
  identifier?: string;
  children?: AstNode[];
  position?: { start: { offset?: number }; end: { offset?: number } };
}
interface NoteLink {
  href: string;
  wiki: boolean;
  start: number;
  end: number;
  wholeStart: number;
  wholeEnd: number;
  alias?: string;
}

export function validateNotePath(path: string): string {
  if (
    path.length > 240 ||
    !/\.md$/i.test(path) ||
    path
      .split("/")
      .some(
        (part) =>
          !part ||
          part.startsWith(".") ||
          /[ .]$/.test(part) ||
          /[<>:"\\|?*\x00-\x1f\x7f]/.test(part) ||
          /^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\..*)?$/i.test(part),
      )
  ) {
    throw new Error("Use a relative .md path without hidden or special names.");
  }
  return path;
}
export function noteTitle(note: Pick<VaultNote, "path" | "body">): string {
  return (
    note.body.match(/^#\s+(.+)$/m)?.[1]?.trim() ||
    note.path.split("/").at(-1)!.replace(/\.md$/i, "")
  );
}
function normalized(path: string): string | null {
  const parts: string[] = [];
  for (const part of path.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (!parts.length) return null;
      parts.pop();
    } else parts.push(part);
  }
  const result = parts.join("/");
  if (!result) return null;
  try {
    return validateNotePath(/\.md$/i.test(result) ? result : result + ".md");
  } catch {
    return null;
  }
}
export function relativeNotePath(from: string, to: string): string {
  const parent = from.split("/").slice(0, -1),
    target = to.split("/");
  while (parent.length && target.length && parent[0] === target[0]) {
    parent.shift();
    target.shift();
  }
  return [...parent.map(() => ".."), ...target].join("/");
}
function encoded(path: string) {
  return encodeURI(path)
    .replace(/#/g, "%23")
    .replace(/\?/g, "%3F")
    .replace(/\(/g, "%28")
    .replace(/\)/g, "%29");
}
export function resolveLink(
  notes: VaultNote[],
  from: string,
  href: string,
  wiki = false,
): { path: string; note?: VaultNote; fragment: string } | null {
  if (
    !href ||
    href.startsWith("#") ||
    /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href)
  )
    return null;
  const hash = href.indexOf("#");
  const fragment = hash < 0 ? "" : href.slice(hash);
  let target: string;
  try {
    target = decodeURIComponent(hash < 0 ? href : href.slice(0, hash));
  } catch {
    return null;
  }
  if (!wiki && /\.[a-z\d]+$/i.test(target) && !/\.md$/i.test(target))
    return null;
  const parent = from.includes("/")
    ? from.slice(0, from.lastIndexOf("/") + 1)
    : "";
  const relative = normalized(
    target.startsWith("/") ? target.slice(1) : parent + target,
  );
  const root = normalized(target.replace(/^\//, ""));
  const candidates =
    wiki && target.includes("/")
      ? [root, relative]
      : [relative, ...(wiki ? [root] : [])];
  for (const path of candidates) {
    const found =
      path && notes.find((n) => n.path.toLowerCase() === path.toLowerCase());
    if (found) return { path: found.path, note: found, fragment };
  }
  if (wiki && !target.includes("/")) {
    const basename = (root || "").toLowerCase();
    const matches = notes.filter(
      (n) => n.path.split("/").at(-1)!.toLowerCase() === basename,
    );
    if (matches.length === 1)
      return { path: matches[0].path, note: matches[0], fragment };
  }
  const path = wiki ? root : relative;
  return path ? { path, fragment } : null;
}

function noteLinks(body: string): NoteLink[] {
  const root = fromMarkdown(body) as unknown as AstNode;
  const links: NoteLink[] = [];
  function walk(node: AstNode) {
    const start = node.position?.start.offset,
      end = node.position?.end.offset;
    if (
      start !== undefined &&
      end !== undefined &&
      (node.type === "link" || node.type === "definition") &&
      node.url
    ) {
      // Positions come from the Markdown parser, so code and image destinations are excluded.
      const afterLabel =
        node.type === "definition"
          ? body.indexOf("]:", start) + 2
          : body.indexOf(
              "(",
              node.children?.at(-1)?.position?.end.offset ?? start,
            ) + 1;
      let first = afterLabel;
      while (/\s/.test(body[first] || "") && first < end) first++;
      let last = first;
      if (body[first] === "<") {
        first++;
        last = body.indexOf(">", first);
      } else {
        let depth = 0;
        while (last < end) {
          const c = body[last];
          if (c === "\\") {
            last += 2;
            continue;
          }
          if (c === "(") depth++;
          if (c === ")") {
            if (!depth) break;
            depth--;
          }
          if (/\s/.test(c) && !depth) break;
          last++;
        }
      }
      if (last >= first)
        links.push({
          href: node.url,
          wiki: false,
          start: first,
          end: last,
          wholeStart: start,
          wholeEnd: end,
        });
    }
    if (node.type === "text" && start !== undefined && end !== undefined) {
      const raw = body.slice(start, end);
      for (const match of raw.matchAll(/\[\[([^\]\n]+)\]\]/g)) {
        const before = raw.slice(0, match.index);
        if ((before.match(/\\+$/)?.[0].length ?? 0) % 2) continue;
        const [href, ...alias] = match[1].split("|");
        const leading = href.length - href.trimStart().length;
        links.push({
          href: href.trim(),
          wiki: true,
          start: start + match.index! + 2 + leading,
          end: start + match.index! + 2 + href.trimEnd().length,
          wholeStart: start + match.index!,
          wholeEnd: start + match.index! + match[0].length,
          alias: alias.length ? alias.join("|") : undefined,
        });
      }
    }
    if (
      !["link", "image", "definition", "code", "inlineCode"].includes(node.type)
    )
      node.children?.forEach(walk);
  }
  walk(root);
  return links.sort((a, b) => a.start - b.start);
}

export function graphFromNotes(notes: VaultNote[]): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const nodes: GraphNode[] = notes.map((n) => ({
    id: n.id,
    path: n.path,
    kind: n.kind,
    title: noteTitle(n),
  }));
  const edges: GraphEdge[] = [],
    seen = new Set<string>();
  for (const note of notes)
    for (const link of noteLinks(note.body)) {
      const target = resolveLink(notes, note.path, link.href, link.wiki);
      if (!target) continue;
      const id = target.note?.id ?? `missing:${target.path.toLowerCase()}`;
      if (id === note.id) continue;
      if (!nodes.some((n) => n.id === id))
        nodes.push({
          id,
          path: target.path,
          kind: "note",
          title: target.path.replace(/\.md$/i, ""),
          missing: true,
        });
      const key = `${note.id}\0${id}`;
      if (!seen.has(key)) {
        edges.push({ source: note.id, target: id });
        seen.add(key);
      }
    }
  return { nodes, edges };
}
function replaceRanges(
  body: string,
  changes: { start: number; end: number; value: string }[],
): string {
  for (const change of changes.sort((a, b) => b.start - a.start))
    body = body.slice(0, change.start) + change.value + body.slice(change.end);
  return body;
}
export function previewMarkdown(note: VaultNote, notes: VaultNote[]): string {
  return replaceRanges(
    note.body,
    noteLinks(note.body)
      .filter((l) => l.wiki)
      .flatMap((link) => {
        const target = resolveLink(notes, note.path, link.href, true);
        if (!target) return [];
        const label = (link.alias ?? link.href).replace(/[\[\]\\]/g, "\\$&");
        return [
          {
            start: link.wholeStart,
            end: link.wholeEnd,
            value: `[${label}](${encoded(relativeNotePath(note.path, target.path))}${target.fragment})`,
          },
        ];
      }),
  );
}
export function renameNote(
  notes: VaultNote[],
  id: string,
  path: string,
): VaultNote[] {
  validateNotePath(path);
  if (
    notes.some(
      (n) => n.id !== id && n.path.toLowerCase() === path.toLowerCase(),
    )
  )
    throw new Error("A note already uses that path.");
  const moved = notes.find((n) => n.id === id);
  if (!moved) throw new Error("Note not found.");
  return notes.map((note) => {
    const from = note.id === id ? path : note.path;
    const changes = noteLinks(note.body).flatMap((link) => {
      const target = resolveLink(notes, note.path, link.href, link.wiki);
      if (!target || (target.note?.id !== id && note.id !== id)) return [];
      const to = target.note?.id === id ? path : target.path;
      const href = link.wiki
        ? to.replace(/\.md$/i, "")
        : encoded(relativeNotePath(from, to));
      return [
        { start: link.start, end: link.end, value: href + target.fragment },
      ];
    });
    return { ...note, path: from, body: replaceRanges(note.body, changes) };
  });
}
export interface Camera {
  x: number;
  y: number;
  scale: number;
}
export function graphPoint(camera: Camera, point: { x: number; y: number }) {
  return {
    x: (point.x - camera.x) / camera.scale,
    y: (point.y - camera.y) / camera.scale,
  };
}
export function zoomAt(
  camera: Camera,
  point: { x: number; y: number },
  factor: number,
): Camera {
  const scale = Math.min(4, Math.max(0.15, camera.scale * factor));
  const graph = graphPoint(camera, point);
  return { x: point.x - graph.x * scale, y: point.y - graph.y * scale, scale };
}
