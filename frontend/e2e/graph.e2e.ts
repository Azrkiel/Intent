import { expect, test } from "@playwright/test";

test("the current project page exposes discussions and editable graph notes before planning", async ({
  page,
}) => {
  await page.goto("/");
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
