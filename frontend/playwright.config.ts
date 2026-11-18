import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:3100" },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/revise",
    env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:3100/api" },
  },
});
