import { expect, test } from "@playwright/test";

const codingHeartbeat = "http://localhost:3000/health";

test("checks both real hosts anonymously and fits a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/status/");

  await expect(page.getByRole("heading", { name: "HackerLeap Status" })).toBeVisible();
  await expect(page.getByText("Operational", { exact: true })).toHaveCount(2);
  await expect(page.getByRole("status")).toContainText("2 of 2 services reachable");
  await expect(page.locator("time")).toHaveAttribute("datetime", /^\d{4}-/);
  await expect(page.getByText("Refresh this page to check the status again.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Status", exact: true })).toHaveAttribute("href", "/status/");

  const websiteDetails = page.locator("summary").filter({ hasText: "Website" });
  await websiteDetails.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Checks whether Django responds.", { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360);
});

test("public status checks the hosted coding platform even with local Django defaults", async ({ page, request }) => {
  await page.route("**/status/", async (route) => {
    const response = await request.get("/status/", { headers: { Host: "www.hackerleap.com" } });
    await route.fulfill({ response });
  });
  await page.route(codingHeartbeat, (route) => route.abort());
  await page.route("https://code.hackerleap.com/health", (route) =>
    route.fulfill({ json: { status: "ok" }, headers: { "Access-Control-Allow-Origin": "*" } }),
  );

  await page.goto("/status/");
  await expect(page.locator("summary").filter({ hasText: "Coding Platform" })).toContainText("Operational");
  await expect(page.getByRole("status")).toContainText("2 of 2 services reachable");
});

test("reports invalid and failing heartbeats independently and recovers on refresh", async ({ page }) => {
  await page.route(codingHeartbeat, (route) =>
    route.fulfill({ status: 200, json: { status: "unexpected" }, headers: { "Access-Control-Allow-Origin": "*" } }),
  );
  await page.goto("/status/");
  await expect(page.locator("summary").filter({ hasText: "Coding Platform" })).toContainText("Not reachable");
  await expect(page.locator("summary").filter({ hasText: "Website" })).toContainText("Operational");
  await expect(page.getByRole("status")).toContainText("1 of 2 services reachable");

  await page.route("**/api/health/", (route) => route.fulfill({ status: 503, json: { status: "ok" } }));
  await page.unroute(codingHeartbeat);
  await page.reload();
  await expect(page.locator("summary").filter({ hasText: "Website" })).toContainText("Not reachable");
  await expect(page.locator("summary").filter({ hasText: "Coding Platform" })).toContainText("Operational");

  await page.unroute("**/api/health/");
  await page.reload();
  await expect(page.getByRole("status")).toContainText("2 of 2 services reachable");
});

test("times out a stalled request without retrying automatically", async ({ page }) => {
  let requests = 0;
  await page.route(codingHeartbeat, () => { requests += 1; });
  await page.goto("/status/");
  await expect(page.locator("summary").filter({ hasText: "Coding Platform" })).toContainText("Checking");
  await expect(page.getByRole("status")).toContainText("1 of 2 services reachable", { timeout: 8000 });
  expect(requests).toBe(1);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("explains how to check service status", async ({ page }) => {
    await page.goto("/status/");
    const fallback = page.locator("noscript p");
    await expect(fallback).toBeVisible();
    await expect(fallback).toHaveText("Enable JavaScript to check service status.");
  });
});
