import { expect, test } from "@playwright/test";

const track = "/tracks/interview-preparation";
const submissions = [
  { id: 1, question_slug: "two-sum", question_title: "Two Sum", language: "java", code: "return result;" },
  { id: 2, question_slug: "reverse-list", question_title: "Reverse List", language: "python", code: "return head" },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("hackerleap-code-admin-token", "test-token"));
  await page.route("**/api/auth/me/", (route) => route.fulfill({
    json: { id: 1, username: "reviewer", email: "", is_staff: true, can_access_coding_platform: true },
  }));
});

test("manual revision shows marked solutions and direct problem links", async ({ page }, testInfo) => {
  await page.route("**/api/revision/", (route) => route.fulfill({ json: submissions.slice(0, 1) }));
  await page.goto("/revise");

  await expect(page.getByRole("heading", { name: "Two Sum" })).toBeVisible();
  await expect(page.getByText("Java 17 solution")).toBeVisible();
  await expect(page.locator("pre")).toContainText("return result;");
  await expect(page.getByRole("link", { name: "Open problem" })).toHaveAttribute("href", "/questions/two-sum");
  if (process.env.REVISION_SCREENSHOTS) {
    await page.screenshot({ path: testInfo.outputPath("manual-revision.png") });
  }
});

test("track revision respects URL tags and preserves navigation context", async ({ page }, testInfo) => {
  await page.route(`**/api${track}/revision/`, (route) => route.fulfill({ json: submissions }));
  await page.route(`**/api${track}/`, (route) => route.fulfill({
    json: { sections: [{ questions: [
      { slug: "two-sum", tags: [{ slug: "arrays", name: "Arrays" }] },
      { slug: "reverse-list", tags: [{ slug: "lists", name: "Linked Lists" }] },
    ] }] },
  }));
  await page.goto(`${track}/revise?tag=missing&source=review`);

  await expect(page.getByRole("heading", { name: "No solved problems match this tag" })).toBeVisible();
  await page.getByRole("button", { name: "Show all solved problems" }).click();
  await expect(page).toHaveURL(/\/revise\?source=review$/);
  await expect(page.getByText("Showing 2 of 2 solved problems")).toBeVisible();

  await page.getByRole("combobox").selectOption("lists");
  await expect(page).toHaveURL(/\/revise\?source=review&tag=lists$/);
  await expect(page.getByText("Showing 1 of 2 solved problems")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Two Sum" })).toHaveCount(0);
  await expect(page.getByText("Latest accepted Python 3 solution")).toBeVisible();
  await expect(page.getByRole("link", { name: "Solve again" })).toHaveAttribute("href", "/questions/reverse-list?from=interview-preparation&tag=lists");
  await expect(page.getByRole("link", { name: "Back to track" })).toHaveAttribute("href", `${track}?tag=lists`);
  if (process.env.REVISION_SCREENSHOTS) {
    await page.screenshot({ path: testInfo.outputPath("track-revision.png") });
  }
});

test("manual revision distinguishes empty results from request errors", async ({ page }) => {
  const endpoint = "**/api/revision/";
  await page.route(endpoint, (route) => route.fulfill({ json: [] }));
  await page.goto("/revise");
  await expect(page.getByRole("heading", { name: "No revision items yet" })).toBeVisible();

  await page.unroute(endpoint);
  await page.route(endpoint, (route) => route.fulfill({ status: 500, json: { detail: "Revision unavailable" } }));
  await page.reload();
  await expect(page.getByText("Revision unavailable")).toBeVisible();
  await expect(page.getByRole("heading", { name: "No revision items yet" })).toHaveCount(0);
});
