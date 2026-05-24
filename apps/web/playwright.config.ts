import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive the real SPA in a browser against a live API.
// Two web servers are started: the FastAPI app on SQLite (migrated) and the
// Vite dev server (which proxies /api -> :8000). Requires browsers to be
// installed once with `npx playwright install chromium`.
const API_DB = "sqlite+aiosqlite:///./e2e.db";
const apiEnv = `DATABASE_URL=${API_DB} ANTHROPIC_API_KEY= ENVIRONMENT=dev`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Fresh migrated SQLite DB, then the API.
      command:
        `bash -c "rm -f e2e.db && ${apiEnv} .venv/bin/alembic upgrade head && ` +
        `${apiEnv} .venv/bin/uvicorn quoteforge_api.main:app --port 8000"`,
      cwd: "../api",
      url: "http://localhost:8000/api/healthz",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
