import { expect, test, type APIRequestContext } from "@playwright/test";

async function approvedDemo(request: APIRequestContext) {
  const response = await request.post("/api/sessions", { data: {} });
  const session = await response.json();
  const base = `/api/sessions/${session.id}`;
  expect(
    (
      await request.post(`${base}/turns`, {
        data: { text: "I want a habit tracker, no login." },
      })
    ).ok(),
  ).toBe(true);
  let current = await (await request.get(base)).json();
  for (let step = 0; step < 8 && !current.gate.ready; step++) {
    expect(current.current_question).toBeTruthy();
    expect(
      (
        await request.post(`${base}/turns`, {
          data: { text: current.current_question.options[0] },
        })
      ).ok(),
    ).toBe(true);
    current = await (await request.get(base)).json();
  }
  expect(current.gate.ready).toBe(true);
  expect((await request.post(`${base}/playback`)).ok()).toBe(true);
  expect(
    (
      await request.post(`${base}/approve`, {
        data: { revision: current.revision },
      })
    ).ok(),
  ).toBe(true);
  return { id: session.id as string, base };
}

test("clarity exposes its scripted framework, proposal labels and reload state", async ({
  page, request,
}, testInfo) => {
  const session = await approvedDemo(request);
  await page.addInitScript(
    (id) => localStorage.setItem("prompt-caller-session", id), session.id,
  );
  await page.goto("/workspace");
  const framework = page.getByRole("region", { name: "Product framework", exact: true });
  await expect(framework).toContainText("Scripted example · no model reasoning");
  await expect(framework).toContainText("Scripted map available");
  await framework.getByText("Explore framework (8 areas)", { exact: true }).click();
  const structure = framework.locator(".framework-area").filter({ hasText: "Components & connections" });
  await structure.locator("summary").click();
  await expect(structure.getByText("Proposal", { exact: true }).first()).toBeVisible();
  await expect(structure.getByText(/Sources: L/).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("framework-desktop.png"), fullPage: true });
  await page.reload();
  await expect(framework).toContainText("Scripted map available");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(framework).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("framework-mobile.png"), fullPage: true });
});

test("the current project page exposes discussions and editable graph notes before planning", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("link", { name: "Workspace", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/workspace$/);
  const project = page.getByRole("button", {
    name: "Project graph",
    exact: true,
  });
  await expect(project).toBeEnabled();
  await project.click();
  await expect(
    page.getByRole("heading", { name: "See the plan. Shape every part." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Graph & notes", exact: true })
    .click();
  await expect(
    page.getByRole("navigation", { name: "Vault notes" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "New note", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Project graph", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Codex execution", exact: true }),
  ).toBeVisible();
});

test("generated plan, discussion, linked Markdown, autosave and reload share the current workspace", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(120_000);
  const session = await approvedDemo(request);
  await page.addInitScript(
    (id) => localStorage.setItem("prompt-caller-session", id),
    session.id,
  );
  await page.goto("/workspace");
  const nav = page.getByRole("navigation", { name: "Workspace", exact: true });
  await nav.getByRole("button", { name: "Project graph", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate phase plan", exact: true })
    .click();
  const graph = page.getByRole("region", { name: "Complete project graph" });
  await expect(graph).toBeVisible({ timeout: 30_000 });
  await page
    .getByRole("button", { name: "Approve this revision", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Export instruction bundle" }),
  ).toBeVisible();
  const canonical = await (await request.get(`${session.base}/plan`)).json();
  await page
    .getByRole("textbox", { name: /Your question for this section/ })
    .fill("Why is this section needed?");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "Section intentions" }),
  ).toContainText("Why is this section needed?");
  await expect(
    nav.getByRole("button", { name: "Project graph", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: testInfo.outputPath("project-graph-desktop.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Graph & notes", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add phase plan", exact: true })
    .click();
  await expect
    .poll(() => page.locator(".vault-node").count())
    .toBeGreaterThan(5);
  await page
    .getByRole("button", { name: "Edit Markdown", exact: true })
    .click();
  const editor = page.getByRole("textbox", {
    name: "Markdown content",
    exact: true,
  });
  await editor.fill((await editor.inputValue()) + "\n\n[[Browser test]]");
  await page
    .getByRole("button", { name: "Browser test, missing note", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create this note", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create note", exact: true })
    .click();
  await editor.fill("# Browser test\n\n[[Plan]]");
  await expect(page.getByText("Saved locally", { exact: true })).toBeVisible();
  const saved = await (await request.get(`${session.base}/vault`)).json();
  expect(saved.source.content_hash).toBe(canonical.plan.content_hash);
  expect(
    saved.notes.find(
      (note: { path: string }) => note.path === "Browser test.md",
    ).body,
  ).toContain("[[Plan]]");
  const unchanged = await (await request.get(`${session.base}/plan`)).json();
  expect(unchanged.planning.approval).toEqual(canonical.planning.approval);
  expect(unchanged.plan.content_hash).toBe(canonical.plan.content_hash);
  await page.screenshot({
    path: testInfo.outputPath("markdown-graph-desktop.png"),
    fullPage: true,
  });
  await page.reload();
  await nav.getByRole("button", { name: "Project graph", exact: true }).click();
  await page
    .getByRole("button", { name: "Graph & notes", exact: true })
    .click();
  await expect(
    page
      .getByRole("navigation", { name: "Vault notes" })
      .getByRole("button", { name: "Browser test", exact: true }),
  ).toBeVisible();
  await nav
    .getByRole("button", { name: "Codex execution", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Build a phase. Review its evidence." }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await nav.getByRole("button", { name: "Project graph", exact: true }).click();
  await expect(graph).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("project-graph-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Graph & notes", exact: true })
    .click();
  await expect(
    page.getByRole("group", { name: /^Interactive graph\./ }),
  ).toBeVisible();
  await expect
    .poll(() => page.locator(".vault-node").count())
    .toBeGreaterThan(5);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("markdown-graph-mobile.png"),
    fullPage: true,
  });
});

test("mobile Markdown graphs have room to explore beside the workspace navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspace");
  await page
    .getByRole("navigation", { name: "Workspace", exact: true })
    .getByRole("button", { name: "Project graph", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Graph & notes", exact: true })
    .click();
  const canvas = page.getByRole("group", { name: /^Interactive graph\./ });
  await expect
    .poll(async () => (await canvas.boundingBox())?.width ?? 0)
    .toBeGreaterThan(220);
  await expect
    .poll(() => page.locator(".vault-node").count())
    .toBeGreaterThan(0);
});
