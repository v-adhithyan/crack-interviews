import { expect, test } from "@playwright/test";

const room = {
  id: "room-123",
  title: "Pairing interview",
  problem_statement: "",
  language: "python",
  code: "def solve():\n    pass\n",
  stdin: "",
  candidate_name: "",
  candidate_email: "",
  candidate_joined: false,
  interviewer_name: "Taylor",
  role: "candidate",
  is_closed: false,
  updated_at: "2026-11-28T00:00:00Z",
};

test("candidate join details stay in the form while the room polls", async ({ page }) => {
  let roomPolls = 0;
  await page.route("**/api/interview-rooms/room-123/", async (route) => {
    if (route.request().method() === "GET") roomPolls += 1;
    await route.fulfill({ json: room });
  });

  await page.goto("/interview/room-123");
  await page.getByLabel("Your name").fill("Sam Candidate");
  await page.getByLabel("Email address").fill("sam@example.org");
  await page.waitForTimeout(1500);

  expect(roomPolls).toBeGreaterThan(1);
  await expect(page.getByLabel("Your name")).toHaveValue("Sam Candidate");
  await expect(page.getByLabel("Email address")).toHaveValue("sam@example.org");
});
