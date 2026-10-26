// @ts-check
const { defineConfig, devices } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:8000'

// Per-run results and report (./al loop). Relative to website/.
const output = process.env.E2E_OUTPUT
const outputDir = output ? `${output}/test-results` : 'test-results'
const html = ['html', { open: 'never', outputFolder: output ? `${output}/playwright-report` : 'playwright-report' }]

module.exports = defineConfig({
  testDir: './e2e',
  globalSetup: require.resolve('./e2e/global-setup'),

  // The app keeps its session in sessionStorage -- one tab's, gone with the
  // tab -- so every test's fresh browser context starts logged out, and each
  // test that needs a session logs in for itself. Tests must not share state.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // Capped locally, not just in CI.
  //
  // `undefined` means one worker per core -- eight here -- and the dev stack
  // is a single uvicorn process running with `--reload`. Under eight workers
  // it intermittently drops connections, surfacing as `socket hang up` on
  // POST /auth/jwt/login in whichever test was unlucky: about one full-suite
  // run in four before the token fixture became worker-scoped, and roughly one
  // in six after. It reads as a flaky application and is the suite outrunning
  // a development server.
  //
  // Four is enough to keep the suite around a minute. The containerised run
  // (`./al test`, test_e2e.yml) starts uvicorn without --reload and does not
  // have this problem; the cap costs it little.
  workers: process.env.CI ? 2 : 4,

  outputDir,
  reporter: process.env.CI ? [['list'], html, ['github']] : [['list'], html],

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
      // 1280x720: wide enough for the desktop workspace (layout/shell.js), so
      // this project runs the whole suite against the docked panels.
      use: { ...devices['Desktop Chrome'] },
      // Two kinds of test belong in a run someone chose to start rather than
      // in the gate on every pull request: performance budgets, which are
      // timing-sensitive, and the recipe walkthroughs, which pause between
      // steps so a person watching the recording can follow. The recipes spec
      // claimed to be excluded here before this line existed to exclude it,
      // and ran in the gate paying for its own pauses. The docs' screenshots
      // (@screens) are the same kind of run.
      grepInvert: /@perf|@recipe|@screens/,
      // The stacked layout's own spec is the phone project's.
      testIgnore: /[\\/]stacked\.spec\.js$/,
    },
    {
      // The phone flow (layout/flow.js), at a phone's size.
      //
      // The editor is one set of panels laid out two ways: docked on a wide
      // screen, stacked one stage at a time on a narrow one. The project above
      // runs everything against the dock; this runs the specs that walk the
      // stages, edit a timeline and follow a render against the stack, so a
      // panel that works in one place and not the other fails here.
      name: 'phone',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
      testMatch: /[\\/](flow|editor|timeline-tools|deliver|stacked)\.spec\.js$/,
      grepInvert: /@perf|@recipe/,
    },
    {
      name: 'perf',
      use: { ...devices['Desktop Chrome'] },
      grep: /@perf/,
    },
    {
      // Records the recipes as video, for the cookbook, and takes the
      // screenshots the docs open with (@screens, screens.spec.js).
      //
      // The docs, the tests and the recipes are one object here: the prose in
      // docs/cookbook.md is generated from these specs, and this project makes
      // the moving pictures the same way. A demonstration recorded from a test
      // cannot drift from the behaviour, because it *is* the behaviour -- and
      // if the recipe breaks, there is no video rather than a stale one.
      //
      // Opt-in, and slower: it runs single-worker so the recording is not
      // competing for the machine, and only over tests tagged @recipe or
      // @screens.
      name: 'docs',
      use: {
        ...devices['Desktop Chrome'],
        video: { mode: 'on', size: { width: 1280, height: 720 } },
        // A steady viewport: a recording that reflows mid-take is not much of
        // a demonstration.
        viewport: { width: 1280, height: 720 },
      },
      grep: /@recipe|@screens/,
      fullyParallel: false,
      workers: 1,
      retries: 0,
    },
  ],
})
