import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./resume-builder-tests",
  use: {
    launchOptions: { executablePath: process.env.RESUME_BROWSER_EXECUTABLE },
  },
});
