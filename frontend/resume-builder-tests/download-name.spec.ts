import { expect, test } from "@playwright/test";

// Use an authenticated local editor URL for a saved draft with a ready PDF job.
const editorUrl = process.env.RESUME_EDITOR_URL;
const session = process.env.RESUME_EDITOR_SESSION;

test("validates the download name and uses it for PDF preview and download", async ({ context, page }) => {
  test.skip(!editorUrl || !session, "Set RESUME_EDITOR_URL and RESUME_EDITOR_SESSION for the local draft.");
  await context.addCookies([{ name: "sessionid", value: session!, url: new URL(editorUrl!).origin }]);
  await page.goto(editorUrl!);
  const name = page.getByRole("textbox", { name: "Download name (optional)" });
  const preview = page.getByRole("button", { name: "Preview PDF", exact: true });
  const download = page.getByRole("button", { name: "Download PDF", exact: true });
  await expect(name).toHaveAttribute("placeholder", "resume");
  await expect(name).toHaveValue("");

  const exportForm = page.locator("form.rb-export");
  for (const button of [preview, download]) {
    for (const invalidName of ["unsafe.pdf", "A".repeat(101)]) {
      await name.fill(invalidName);
      expect(await name.evaluate((input: HTMLInputElement) => input.validity.patternMismatch)).toBe(true);
      await button.click();
      expect(context.pages()).toHaveLength(1);
    }
  }

  // Keep exports in this page so Playwright can observe the automatic download.
  await exportForm.evaluate((form) => form.removeAttribute("target"));
  await name.fill("My Resume_2026-v2");
  const previewPage = page.waitForResponse((response) =>
    new URL(response.url()).searchParams.get("download_name") === "My Resume_2026-v2"
    && response.request().isNavigationRequest() && response.status() === 200);
  await preview.click();
  await previewPage;
  await expect(page.locator("#pdf-ready")).toHaveAttribute("href", /download_name=My\+Resume_2026-v2$/);

  for (const [value, expected] of [["My Resume_2026-v2", "My Resume_2026-v2.pdf"], ["", "resume.pdf"]]) {
    await page.goto(editorUrl!);
    await exportForm.evaluate((form) => form.removeAttribute("target"));
    await name.fill(value);
    const downloaded = page.waitForEvent("download");
    await download.click();
    expect((await downloaded).suggestedFilename()).toBe(expected);
  }
});
