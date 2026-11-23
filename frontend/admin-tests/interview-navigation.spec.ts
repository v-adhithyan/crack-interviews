import { expect, test } from "@playwright/test";

test("product navigation keeps system design interviews after simulator removal", async ({ page }) => {
  await page.goto("/admin/login/");
  await page.getByLabel("Username").fill("admin-browser");
  await page.getByLabel("Password").fill("local-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/admin\/$/);

  await page.goto("/app/resume-builder/");
  const navigation = page.getByRole("navigation", { name: "Dashboard" });
  await expect(navigation).toBeVisible();
  if (process.env.INTERVIEW_NAV_SCREENSHOT) {
    await page.locator("#product-sidebar").screenshot({ path: process.env.INTERVIEW_NAV_SCREENSHOT });
  }
  await expect(navigation.getByRole("link", { name: /simulator/i })).toHaveCount(0);
  await navigation.getByRole("link", { name: "System Design Interview", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/mock-interview\/$/);
  await navigation.getByRole("link", { name: "System Design History", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/mock-interview\/history\/$/);
  await expect(page.getByText("System design", { exact: true })).toBeVisible();
});
