import { defineConfig } from "@playwright/test";

/**
 * Smoke test against the production build. Needs the Spring Boot API running
 * (API_ORIGIN, default http://localhost:8080) with at least one job in the DB.
 *   npm run build && npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run start",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
