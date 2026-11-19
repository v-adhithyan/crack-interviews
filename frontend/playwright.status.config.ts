import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./status-tests",
  use: {
    baseURL: "http://127.0.0.1:8100",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
  },
  webServer: [
    {
      command: "python manage.py runserver 127.0.0.1:8100 --noreload",
      cwd: "../backend",
      env: { DJANGO_ALLOWED_HOSTS: "localhost,127.0.0.1,www.hackerleap.com" },
      url: "http://127.0.0.1:8100/api/health/",
    },
    {
      command: "npm run dev -- --hostname localhost --port 3000",
      url: "http://localhost:3000/health",
    },
  ],
});
