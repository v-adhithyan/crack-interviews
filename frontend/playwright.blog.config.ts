import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./blog-tests",
  use: {
    baseURL: "http://127.0.0.1:8118",
    viewport: { width: 1440, height: 1000 },
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
  },
  webServer: {
    command: "python manage.py migrate --noinput && python manage.py runserver 127.0.0.1:8118 --noreload",
    cwd: "../backend",
    env: { DJANGO_SETTINGS_MODULE: "config.settings.dev" },
    url: "http://127.0.0.1:8118/",
  },
});
