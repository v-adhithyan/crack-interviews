import { expect, test } from "@playwright/test";

test("configures and replaces a write-only ChatGPT key from the profile menu", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Email or username").fill("portal-test");
  await page.getByLabel("Password").fill("browser-test-password");
  await page.getByRole("button", { name: "Login" }).click();

  await page.getByLabel("Open user menu").click();
  if (process.env.AI_SCREENSHOTS_DIR) {
    await page.screenshot({ path: `${process.env.AI_SCREENSHOTS_DIR}/profile-after.png` });
  }
  await page.getByRole("link", { name: /Settings.*Integrations.*AI/ }).click();
  await expect(page.getByRole("heading", { name: "AI", exact: true })).toBeVisible();

  const provider = page.getByLabel("Provider");
  const key = page.getByLabel(/^API key:?$/);
  await provider.selectOption("claude");
  await expect(page.getByText("Claude is currently unsupported. Choose ChatGPT.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save API key" })).toBeDisabled();

  await provider.selectOption("chatgpt");
  await expect(key).toHaveAttribute("type", "password");
  await key.fill("test-first-key");
  await page.getByRole("button", { name: "Save API key" }).click();
  await expect(page.getByText("A ChatGPT API key is configured.")).toBeVisible();
  await expect(key).toHaveValue("");
  if (process.env.AI_SCREENSHOTS_DIR) {
    await page.screenshot({ path: `${process.env.AI_SCREENSHOTS_DIR}/settings-after.png` });
  }

  await key.fill("test-replacement-key");
  await page.getByRole("button", { name: "Replace API key" }).click();
  await expect(page.getByText("ChatGPT API key saved.")).toBeVisible();
  await expect(key).toHaveValue("");
});
