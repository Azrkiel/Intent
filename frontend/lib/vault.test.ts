import { describe, expect, it } from "vitest";
import {
  graphFromNotes,
  renameNote,
  previewMarkdown,
  resolveLink,
  zoomAt,
  graphPoint,
  type VaultNote,
} from "./vault";

const note = (id: string, path: string, body = ""): VaultNote => ({
  id,
  path,
  body,
  kind: id === "plan" ? "plan" : "note",
});

describe("Markdown vault links", () => {
  it("ignores unused reference definitions and bounds missing-node expansion", () => {
    expect(
      graphFromNotes([note("plan", "Plan.md", "[unused]: Missing.md")]).edges,
    ).toHaveLength(0);
    const graph = graphFromNotes([
      note(
        "plan",
        "Plan.md",
        Array.from({ length: 800 }, (_, i) => `[[Missing-${i}]]`).join(" "),
      ),
    ]);
    expect(graph.nodes.length).toBeLessThanOrEqual(750);
    expect(graph.truncated).toBe(true);
  });
  it("builds edges from real inline, reference and wiki links, skipping code, images and external URLs", () => {
    const notes = [
      note(
        "plan",
        "Plan.md",
        "[One](notes/One.md#hello) [[Two|Second]]\n\n[again][ref]\n\n[ref]: notes/One.md\n\n`[[Fake]]` ![image](Image.md) [web](https://example.com) [section](#here)\n\n```md\n[[Also fake]]\n```",
      ),
      note("one", "notes/One.md"),
      note("two", "Two.md"),
    ];
    const graph = graphFromNotes(notes);
    expect(graph.nodes.map((n) => n.id).sort()).toEqual(["one", "plan", "two"]);
    expect(graph.edges).toEqual([
      { source: "plan", target: "one" },
      { source: "plan", target: "two" },
    ]);
  });
  it("resolves relative links, vault wiki paths, aliases, encoded spaces and unique basenames", () => {
    const notes = [
      note("plan", "Plan.md"),
      note("a", "notes/An idea.md"),
      note("b", "notes/Two.md"),
    ];
    expect(
      resolveLink(notes, "notes/Two.md", "An%20idea.md#more")?.note?.id,
    ).toBe("a");
    expect(resolveLink(notes, "Plan.md", "An idea", true)?.note?.id).toBe("a");
    expect(resolveLink(notes, "notes/Two.md", "../Plan.md")?.note?.id).toBe(
      "plan",
    );
    expect(resolveLink(notes, "Plan.md", "../../escape.md")).toBeNull();
    expect(resolveLink(notes, "Plan.md", "javascript:alert(1)")).toBeNull();
  });
  it("keeps unresolved links as shared placeholders and ignores escaped wiki syntax", () => {
    const graph = graphFromNotes([
      note(
        "plan",
        "Plan.md",
        "[[Missing]] [[Missing#Heading|Alias]] \\[[Escaped]]",
      ),
    ]);
    expect(graph.nodes.filter((n) => n.missing).map((n) => n.path)).toEqual([
      "Missing.md",
    ]);
    expect(graph.edges).toHaveLength(1);
  });
  it("does not guess between ambiguous wikilink basenames", () => {
    const notes = [note("a", "a/Idea.md"), note("b", "b/Idea.md")];
    expect(resolveLink(notes, "Plan.md", "Idea", true)?.note).toBeUndefined();
    expect(resolveLink(notes, "a/Other.md", "Idea", true)?.note?.id).toBe("a");
  });
  it("turns wiki aliases into safe preview links without touching code", () => {
    const notes = [
      note("plan", "Plan.md", "[[notes/An idea#Hello|Read this]] `[[Code]]`"),
      note("a", "notes/An idea.md"),
    ];
    expect(previewMarkdown(notes[0], notes)).toBe(
      "[Read this](notes/An%20idea.md#Hello) `[[Code]]`",
    );
  });
});

describe("safe note renaming", () => {
  it("updates incoming Markdown/wiki/reference destinations and keeps aliases, titles, code and external links", () => {
    const notes = [
      note(
        "plan",
        "Plan.md",
        '[One](notes/One.md#h "Title") [[One|Alias]]\n\n[ref][one]\n\n[one]: notes/One.md\n\n`[[One]]` [web](https://example.com/One.md)',
      ),
      note("one", "notes/One.md", "[Back](../Plan.md)"),
    ];
    const updated = renameNote(notes, "one", "archive/New.md");
    expect(updated[0].body).toContain(
      '[One](archive/New.md#h "Title") [[archive/New|Alias]]',
    );
    expect(updated[0].body).toContain("[one]: archive/New.md");
    expect(updated[0].body).toContain(
      "`[[One]]` [web](https://example.com/One.md)",
    );
    expect(updated[1].body).toBe("[Back](../Plan.md)");
  });
  it("preserves outgoing links when moving a note to another folder", () => {
    const notes = [
      note("plan", "Plan.md"),
      note("one", "One.md", "[Plan](Plan.md) [Missing](Missing.md) [[Plan]]"),
    ];
    const updated = renameNote(notes, "one", "deep/folder/One.md");
    expect(updated[1].body).toBe(
      "[Plan](../../Plan.md) [Missing](../../Missing.md) [[Plan]]",
    );
  });
  it("rejects collisions and paths outside the vault", () => {
    const notes = [note("plan", "Plan.md"), note("one", "One.md")];
    expect(() => renameNote(notes, "one", "PLAN.md")).toThrow();
    expect(() => renameNote(notes, "one", "../One.md")).toThrow();
    expect(() => renameNote(notes, "one", "NUL.md")).toThrow();
  });
});

describe("graph navigation", () => {
  it("zooms around the pointer without moving the underlying graph point", () => {
    const camera = { x: 30, y: -20, scale: 1.5 };
    const point = { x: 130, y: 100 };
    expect(graphPoint(zoomAt(camera, point, 2), point)).toEqual(
      graphPoint(camera, point),
    );
    expect(zoomAt(camera, point, 100).scale).toBe(4);
    expect(zoomAt(camera, point, 0.001).scale).toBe(0.15);
  });
});
