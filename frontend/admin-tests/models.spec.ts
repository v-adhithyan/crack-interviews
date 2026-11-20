import { expect, test } from "@playwright/test";

test("new model lists are reachable from the Django admin index", async ({ page }) => {
  await page.goto("/admin/");
  await page.getByLabel("Username").fill("admin-browser");
  await page.getByLabel("Password").fill("local-test-password");
  await page.getByRole("button", { name: "Log in" }).click();

  const modelLists = [
    "core/testcaseresult",
    "product/aiintegration",
    "product/analysisfollowup",
    "product/interviewsimulatorsession",
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
