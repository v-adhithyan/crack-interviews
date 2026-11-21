import { expect, test } from "@playwright/test";

test("a superuser can view and open related records below the user form", async ({ page }) => {
  await page.goto("/admin/auth/user/?q=admin-browser");
  await page.getByLabel("Username").fill("admin-browser");
  await page.getByLabel("Password").fill("local-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await page.getByRole("link", { name: "admin-browser", exact: true }).click();

  const related = page.getByRole("region", { name: "Related records" });
  await expect(related).toBeVisible();
  await expect(page.locator("#content-main + #user-related-records")).toBeVisible();
  await expect(related.getByRole("heading", { name: "Mock interview sessions" })).toBeVisible();
  const draft = related.locator('a[href^="/admin/product/resumedraft/"]');
  await expect(draft).toHaveCount(1);
  await draft.click();
  await expect(page).toHaveURL(/\/admin\/product\/resumedraft\/\d+\/change\/$/);
  await expect(page.getByRole("heading", { name: "View resume draft" })).toBeVisible();
});

test("new model lists are reachable from the Django admin index", async ({ page }) => {
  await page.goto("/admin/");
  await page.getByLabel("Username").fill("admin-browser");
  await page.getByLabel("Password").fill("local-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator("#content-main")).toBeVisible();

  const hiddenModels = [
    "aiintegration",
    "analysisfollowup",
    "interviewsimulatorsession",
    "mockinterviewsession",
    "mockinterviewturn",
  ];

  for (const model of hiddenModels) {
    await expect(page.locator(`#content-main a[href="/admin/product/${model}/"]`)).toHaveCount(0);
  }

  const modelLists = [
    "core/testcaseresult",
    "product/publicbuildercounter",
    "product/publicbuildergate",
    "product/publicresumepdfjob",
    "product/publicresumetransfer",
    "product/resumedraft",
    "product/resumeeditapplication",
    "product/resumepdfjob",
    "product/resumepruneplan",
  ];

  for (const model of modelLists) {
    const url = `/admin/${model}/`;
    await page.locator(`#content-main th a[href="${url}"]`).click();
    await expect(page).toHaveURL(url);
    await expect(page.locator("#changelist")).toBeVisible();
    await page.goBack();
  }
});
