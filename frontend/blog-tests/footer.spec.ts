import { expect, test } from "@playwright/test";

const comparisons = ["canva", "novoresume", "resume-io", "teal", "zety"];

test.beforeEach(async ({ page, baseURL }) => {
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === baseURL ? route.continue() : route.abort(),
  );
  await page.goto("/");
});

test("the home footer opens all five resume comparison articles", async ({ page }, testInfo) => {
  const footer = page.locator("footer.site-footer");
  const links = footer.getByRole("link", { name: /^HackerLeap vs\./ });
  await expect(links).toHaveCount(comparisons.length);
  await footer.screenshot({ path: testInfo.outputPath("footer-after.png") });

  for (const comparison of comparisons) {
    const path = `/blog/hackerleap-vs-${comparison}/`;
    const link = footer.locator(`a[href="${path}"]`);
    const title = await link.innerText();
    await link.click();
    await expect(page).toHaveURL(path);
    const article = page.locator("article.blog-article");
    await expect(article.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(article.locator(".blog-article-body").getByRole("heading", { level: 2 }).first()).toBeVisible();
    await article.screenshot({ path: testInfo.outputPath(`hackerleap-vs-${comparison}.png`) });
    await page.goBack();
  }
});

test("comparison links fit in the mobile footer", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const footer = page.locator("footer.site-footer");
  const links = footer.getByRole("link", { name: /^HackerLeap vs\./ });
  await expect(links).toHaveCount(comparisons.length);
  expect(await footer.evaluate((element) => element.scrollWidth)).toBeLessThanOrEqual(390);
  await links.last().click();
  await expect(page).toHaveURL("/blog/hackerleap-vs-zety/");
});
