import { expect, test } from "@playwright/test";

test("the last registration closes signup for the next visitor", async ({ browser, page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/signup/");
  await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("signup-before.png"), fullPage: true });

  await page.getByLabel("Username").fill("last-candidate");
  await page.getByLabel("Email").fill("last-candidate@example.com");
  await page.getByLabel("Password:", { exact: true }).fill("BrowserTest!100");
  await page.getByLabel("Password confirmation").fill("BrowserTest!100");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).not.toHaveURL(/\/signup\//);

  const visitor = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const response = await visitor.goto(new URL("/signup/", page.url()).href);
  expect(response?.status()).toBe(429);
  await expect(visitor.getByText("Today's signup limit has been reached.", { exact: false })).toBeVisible();
  await expect(visitor.locator("time")).toHaveText(/^12:00 AM, .+ IST$/);
  await expect(visitor.locator("form")).toHaveCount(0);
  await expect(visitor.getByRole("link", { name: /sign in/i }).last()).toBeVisible();
  await visitor.screenshot({ path: testInfo.outputPath("signup-after.png"), fullPage: true });
  await visitor.close();
});
