import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./admin-tests",
  use: {
    baseURL: "http://127.0.0.1:8133",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
  },
  webServer: {
    command: "python ../frontend/admin-tests/serve.py",
    cwd: "../backend",
    url: "http://127.0.0.1:8133/admin/login/",
  },
});
