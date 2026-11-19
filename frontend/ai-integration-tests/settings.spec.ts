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

test("staff can open the shared integration from the profile menu", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Email or username").fill("staff-test");
  await page.getByLabel("Password").fill("browser-test-password");
  await page.getByRole("button", { name: "Login" }).click();

  await page.getByLabel("Open user menu").click();
  const settings = page.getByRole("link", { name: /Settings.*Integrations.*AI/ });
  await expect(settings).toBeVisible();
  if (process.env.AI_REVIEW_SCREENSHOTS_DIR) {
    await page.screenshot({ path: `${process.env.AI_REVIEW_SCREENSHOTS_DIR}/staff-profile.png` });
  }
  await settings.click();
  await expect(page.getByText("Your account uses the shared ChatGPT integration.")).toBeVisible();
  await expect(page.getByLabel(/^API key:?$/)).toHaveCount(0);
  if (process.env.AI_REVIEW_SCREENSHOTS_DIR) {
    await page.screenshot({ path: `${process.env.AI_REVIEW_SCREENSHOTS_DIR}/staff-settings.png` });
  }
});

test("a newly registered user without a key can generate a manual analysis prompt", async ({ page, context }) => {
  await page.goto("/signup/");
  await page.getByLabel("Username").fill("new-candidate");
  await page.getByLabel("Email").fill("new-candidate@example.com");
  await page.getByLabel("Password:", { exact: true }).fill("BrowserTest!100");
  await page.getByLabel("Password confirmation").fill("BrowserTest!100");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).not.toHaveURL(/\/signup\//);

  const resume = await context.newPage();
  await resume.setContent("<h1>Test Candidate</h1><p>Experienced Python and Django developer.</p>");
  const pdf = await resume.pdf();
  await resume.close();

  await page.goto("/app/");
  await page.locator('input[type="file"][name="resume"]').setInputFiles({
    name: "test-resume.pdf", mimeType: "application/pdf", buffer: pdf,
  });
  await page.getByRole("button", { name: "Upload Resume" }).click();
  await page.getByLabel("Job Description").fill("We need an experienced Python and Django developer.");
  await page.getByRole("button", { name: "Analyze Now" }).click();
  const outcome = page.getByText(/Prompt generated\. Copy it/);
  await expect(outcome).toBeVisible();
  if (process.env.AI_REVIEW_SCREENSHOTS_DIR) {
    await page.screenshot({ path: `${process.env.AI_REVIEW_SCREENSHOTS_DIR}/new-user.png`, fullPage: true });
  }
  await expect(page.getByLabel("Generated prompt")).toHaveValue(/experienced Python and Django developer/);
  await expect(page.getByRole("textbox", { name: "Analysis JSON" })).toBeVisible();
});
