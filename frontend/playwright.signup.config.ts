import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./signup-tests",
  use: {
    baseURL: "http://127.0.0.1:8101",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
  },
  webServer: {
    command: "python ../frontend/signup-tests/serve.py",
    cwd: "../backend",
    url: "http://127.0.0.1:8101/signup/",
  },
});
