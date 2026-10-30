import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ClarityPanel } from "../components/clarity-panel";
import type { Session } from "./types";

const field = (name: string, failing: string[]) => ({
  field: name,
  text: "Only me, on my laptop",
  text_hash: "h".repeat(64),
  alpha: 1,
  judgement: { readback: "You alone use it on your laptop." },
  failing,
  passed: failing.length === 0,
});

const session = {
  mode: "live",
  revision: 2,
  clarity_version: 2,
  turns: [{ number: 1, text: "x" }],
  gate: {
    ready: false,
    blockers: ["North Star Job: confirm Intent's read-back"],
  },
  clarity: {
    revision: 2,
    mode: "live",
    source_hash: "a".repeat(64),
    fatigued: false,
    downstream_complete: true,
    fields: [field("who-when", []), field("job", ["G3"])],
    claims: [
      {
        id: "C7",
        text: "Keep the list in this browser's storage",
        tags: ["data/storage"],
        status: "proposal",
        spans: [],
        flags: [],
      },
    ],
    review: { canaries: [1, 2, 3], caught: ["a", "b", "c"], trusted: true },
    scenarios: [
      {
        id: "S1",
        title: "Add a link",
        given: "an empty list",
        when: "I add a link",
        then: "it shows first",
        claims: ["C1"],
        kind: "journey",
      },
    ],
    decisions: [
      {
        id: "D-P1",
        status: "delegated",
        question: "Allow duplicates?",
        options: ["Yes", "No"],
        outcome: "Yes",
        because: "good: 3 of 4 candidate builds chose this",
        reversibility: "two-way",
        due_phase: null,
      },
    ],
  },
  clarity_readout: {
    statements: 4,
    unmapped_words: 0,
    choices_made: 1,
    decisions_open: 0,
    scenarios: 1,
  },
} as unknown as Session;

function render(value = session) {
  return renderToStaticMarkup(
    createElement(ClarityPanel, {
      session: value,
      busy: false,
      disabled: false,
      onConfirm() {},
      onCorrect() {},
      onVeto() {},
      onReaderVariation() {},
      onRetry() {},
    }),
  );
}

describe("clarity panel", () => {
  it("shows fields, the pending read-back, choices with veto, scenarios and review recall", () => {
    const html = render();
    expect(html).toContain("Who &amp; when");
    expect(html).toContain("You alone use it on your laptop.");
    expect(html).toContain("That&#x27;s right");
    expect(html).toContain("Choices I made for you (1)");
    expect(html).toContain("What I filled in for you (1)");
    expect(html).toContain("Keep the list in this browser");
    expect(html).toContain("Veto");
    expect(html).toContain("Add a link");
    expect(html).toContain("caught 3 of 3 planted defects");
    expect(html).toContain("4 statements mapped");
  });

  it("labels demo output as scripted", () => {
    expect(render({ ...session, mode: "demo" })).toContain(
      "Scripted example · no model reasoning",
    );
  });

  it("labels the reader check and selects the session's mode", () => {
    const html = render({ ...session, clarity_reader_variation: "tier" });
    expect(html).toContain("Reader check:");
    for (const label of [
      "Different perspective",
      "Different temperature",
      "Different model",
    ])
      expect(html).toContain(label);
    expect(html).toMatch(/<option value="tier" selected/);
    expect(render()).toMatch(/<option value="perspective" selected/);
  });

  it("disables the selector while busy", () => {
    const html = renderToStaticMarkup(
      createElement(ClarityPanel, {
        session,
        busy: true,
        disabled: false,
        onConfirm() {},
        onCorrect() {},
        onVeto() {},
        onReaderVariation() {},
        onRetry() {},
      }),
    );
    expect(html).toMatch(/<select[^>]*disabled/);
  });

  it("hides stale clarity", () => {
    const html = render({ ...session, revision: 3 });
    expect(html).toContain("Needs a fresh check");
    expect(html).not.toContain("Add a link");
  });
});
