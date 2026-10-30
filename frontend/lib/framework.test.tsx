import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { FrameworkReviewPanel } from "../components/framework-review";
import type { Session } from "./types";

const session = {
  mode: "live", revision: 3, turns: [{ number: 1, text: "A habit tracker" }],
  gate: { ready: false, blockers: ["Map journeys: completion."] },
  framework_review: {
    revision: 3, mode: "live", source_hash: "a".repeat(64),
    framework: {
      sections: [{ area: "journeys", entries: [{
        aspect: "actions", text: "Create a habit, then mark today's completion.",
        status: "proposal", ledger_ids: ["L2"],
      }] }], questions: [],
    },
    assessment: { reviewed_entry_ids: ["journeys.0"], reviewed_areas: ["journeys"], issues: [], questions: [] },
  },
} as unknown as Session;

function render(value = session) {
  return renderToStaticMarkup(createElement(FrameworkReviewPanel, {
    session: value, busy: false, disabled: false, onRetry() {},
  }));
}

describe("framework visibility", () => {
  it("shows the map, proposal labels, citations and server blockers", () => {
    const html = render();
    expect(html).toContain("Product framework");
    expect(html).toContain("Create a habit");
    expect(html).toContain("Proposal");
    expect(html).toContain("L2");
    expect(html).toContain("Map journeys: completion.");
    expect(html).toContain("Review framework again");
  });

  it("labels scripted examples without claiming live reasoning", () => {
    const html = render({ ...session, mode: "demo" });
    expect(html).toContain("Scripted example");
    expect(html).toContain("no model reasoning");
  });

  it("does not present a stale framework as current or reveal its entries", () => {
    const html = render({ ...session, revision: 4 });
    expect(html).toContain("Needs a fresh review");
    expect(html).not.toContain("Create a habit");
  });

  it("explains that a live framework has not been reviewed yet", () => {
    const html = render({ ...session, framework_review: null });
    expect(html).toContain("Framework review required");
    expect(html).not.toContain("Mapped and reviewed");
  });
});
