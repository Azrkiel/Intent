import { expect, test } from "@playwright/test";

test("clarity v2 confirms read-backs and approves scenarios", async ({
  page,
  request,
}, testInfo) => {
  const session = await (
    await request.post("/api/sessions", { data: { clarity_version: 2 } })
  ).json();
  const base = `/api/sessions/${session.id}`;
  expect(
    (
      await request.post(`${base}/turns`, {
        data: { text: "I want a habit tracker, no login." },
      })
    ).ok(),
  ).toBe(true);
  let current = await (await request.get(base)).json();
  for (let step = 0; step < 16 && !current.gate.ready; step++) {
    const pending = (current.clarity?.fields ?? []).find(
      (f: { failing: string[] }) =>
        f.failing.length === 1 && f.failing[0] === "G3",
    );
    if (pending) {
      expect(
        (
          await request.post(`${base}/clarity/readback`, {
            data: {
              field: pending.field,
              text_hash: pending.text_hash,
              revision: current.revision,
            },
          })
        ).ok(),
      ).toBe(true);
    } else {
      expect(current.current_question).toBeTruthy();
      expect(
        (
          await request.post(`${base}/turns`, {
            data: { text: current.current_question.options[0] },
          })
        ).ok(),
      ).toBe(true);
    }
    current = await (await request.get(base)).json();
  }
  expect(current.gate.ready).toBe(true);
  // The demo asked North Star and decision questions, never the v1 slot lenses.
  const lenses = current.questions.map(
    (entry: { question: { lens: string } }) => entry.question.lens,
  );
  expect(lenses).toContain("north-star");
  expect(lenses).toContain("decision");
  expect(lenses).not.toContain("edges");
  const texts = current.clarity.fields.map((f: { text: string }) => f.text);
  expect(texts.every(Boolean)).toBe(true);
  expect(new Set(texts).size).toBe(6);
  await page.addInitScript(
    (id) => localStorage.setItem("prompt-caller-session", id),
    session.id,
  );
  await page.goto("/workspace");
  const panel = page.getByRole("region", { name: "Clarity", exact: true });
  await expect(panel).toContainText("Scripted example · no model reasoning");
  await expect(panel).toContainText("scenarios to confirm");
  for (const text of texts) await expect(panel).toContainText(text);
  await expect(panel.getByText("Scenarios to approve (2)")).toBeVisible();
  await expect(
    panel.getByRole("group").filter({ hasText: "Scenarios to approve" }),
  ).toHaveAttribute("open", "");
  await expect(
    page.getByRole("button", { name: "Review brief", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("clarity-desktop.png"),
    fullPage: true,
  });
  // The primary step is explicit scenario approval; it leads to the approval card.
  const cta = page.getByRole("button", {
    name: "Approve scenarios",
    exact: true,
  });
  await expect(cta).toBeVisible();
  await panel.screenshot({ path: testInfo.outputPath("panel-desktop.png") });
  await page.screenshot({
    path: testInfo.outputPath("approve-cta.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await panel.screenshot({ path: testInfo.outputPath("panel-mobile.png") });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await cta.click();
  const card = page.locator("#scenario-approval");
  await expect(card).toContainText("Your scenarios.");
  await expect(card).toBeFocused();
  await card
    .getByRole("button", { name: "Approve scenarios", exact: true })
    .click();
  await expect(page.getByText("CLAUDE.md").first()).toBeVisible();
  // Once approved, the clarify step offers the brief instead.
  const nav = page.getByRole("navigation", { name: "Workspace", exact: true });
  await nav.getByRole("button", { name: "Conversation", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Review brief", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve scenarios", exact: true }),
  ).toHaveCount(0);
  await nav.getByRole("button", { name: "Build brief", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("clarity-mobile.png"),
    fullPage: true,
  });
});
