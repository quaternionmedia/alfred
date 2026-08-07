// @ts-check
const { defineConfig, devices } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:8000'

module.exports = defineConfig({
  testDir: './e2e',
  globalSetup: require.resolve('./e2e/global-setup'),

  // The app holds auth in memory rather than in a cookie or storage, so each
  // test that needs a session logs in for itself. Tests must not share state.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,

  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never' }], ['github']]
    : [['list'], ['html', { open: 'never' }]],

  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL,
    viewport: { width: 1200, height: 800 },
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      // Performance budgets are timing-sensitive and belong in a run someone
      // chose to start, not in the gate on every pull request.
      grepInvert: /@perf/,
    },
    {
      name: 'perf',
      use: { ...devices['Desktop Chrome'] },
      grep: /@perf/,
    },
  ],
})
