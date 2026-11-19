import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./ai-integration-tests",
  use: {
    baseURL: "http://127.0.0.1:8102",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
  },
  webServer: {
    command: "python ../frontend/ai-integration-tests/serve.py",
    cwd: "../backend",
    url: "http://127.0.0.1:8102/login/",
  },
});
