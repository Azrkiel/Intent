import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:3817",
    viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8817",
      cwd: path.resolve(__dirname, ".."),
      url: "http://127.0.0.1:8817/api/health",
      env: {
        PROMPT_CALLER_MODE: "demo",
        FRONTEND_PORT: "3817",
        DATABASE_PATH: `.data/graph-e2e-${Date.now()}.sqlite3`,
      },
    },
    {
      command:
        "node ../node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3817",
      url: "http://127.0.0.1:3817",
      env: { INTENT_API_PORT: "8817", NEXT_TELEMETRY_DISABLED: "1" },
      timeout: 120_000,
    },
  ],
});
