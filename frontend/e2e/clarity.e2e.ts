import { expect, test } from "@playwright/test";

test("clarity v2 confirms read-backs and approves scenarios", async ({ page, request }, testInfo) => {
  const session = await (await request.post("/api/sessions", { data: { clarity_version: 2 } })).json();
  const base = `/api/sessions/${session.id}`;
  expect((await request.post(`${base}/turns`, { data: { text: "I want a habit tracker, no login." } })).ok()).toBe(true);
  let current = await (await request.get(base)).json();
  for (let step = 0; step < 16 && !current.gate.ready; step++) {
    const pending = (current.clarity?.fields ?? []).find(
      (f: { failing: string[] }) => f.failing.length === 1 && f.failing[0] === "G3",
    );
    if (pending) {
      expect((await request.post(`${base}/clarity/readback`, {
        data: { field: pending.field, text_hash: pending.text_hash, revision: current.revision },
      })).ok()).toBe(true);
    } else {
      expect(current.current_question).toBeTruthy();
      expect((await request.post(`${base}/turns`, { data: { text: current.current_question.options[0] } })).ok()).toBe(true);
    }
    current = await (await request.get(base)).json();
  }
  expect(current.gate.ready).toBe(true);
  await page.addInitScript((id) => localStorage.setItem("prompt-caller-session", id), session.id);
  await page.goto("/workspace");
  const panel = page.getByRole("region", { name: "Clarity", exact: true });
  await expect(panel).toContainText("Scripted example · no model reasoning");
  await expect(panel).toContainText("scenarios to confirm");
  await page.screenshot({ path: testInfo.outputPath("clarity-desktop.png"), fullPage: true });
  const nav = page.getByRole("navigation", { name: "Workspace", exact: true });
  await nav.getByRole("button", { name: "Build brief", exact: true }).click();
  await page.getByRole("button", { name: "Approve scenarios", exact: true }).click();
  await expect(page.getByText("Build brief").first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath("clarity-mobile.png"), fullPage: true });
});
