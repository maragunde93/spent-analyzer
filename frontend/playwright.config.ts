import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  workers: 1,
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.03 }
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: "pnpm dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120_000
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 } } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } }
  ]
});
