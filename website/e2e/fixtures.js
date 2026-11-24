const { test: base, expect, request } = require('@playwright/test')
const { CREDENTIALS } = require('./credentials')

/**
 * Log in through the UI and assert it worked.
 *
 * Playwright's usual shortcut -- log in once via the API, save `storageState`,
 * reuse it -- is not available here. The app keeps its JWT in sessionStorage
 * (`User` in `src/User.js`), which survives a reload in the same tab and ends
 * with the tab; `storageState` carries cookies and localStorage, and neither
 * holds a credential, so there is nothing to seed. The Cypress suite's
 * `auth.js` tried exactly that shortcut and is commented out in its entirety,
 * which is consistent with it never having worked.
 *
 * The success signal is the menu link's *text*, not its presence. The link is
 * rendered unconditionally and only swaps between "Login" and "Logout"
 * (`src/Menu.js`), so asserting it is visible -- as the Cypress suite did --
 * cannot fail in either state.
 *
 * Note the selector is `a.loginLink`, not `#login-link`. The header used to
 * render two link sets from the same components, so several ids appeared
 * twice on every page; `SELECTORS` resolved each to exactly one element. The
 * duplication is gone, and the session link now lives in the footer rather
 * than the header, but addressing it by class is still the stable choice.
 */
const SELECTORS = {
  login: 'a.loginLink',
  // The stage rail is the navigation. The header carried PROJECTS and
  // RENDERS, which pointed at two of the four stages the rail already lists.
  stages: '.stagerail .stage',
}

async function login(page, creds = CREDENTIALS) {
  await page.goto('/')
  await page.locator(SELECTORS.login).click()

  await page.locator('#username').fill(creds.username)
  await page.locator('#password').fill(creds.password)
  await page.locator('#submit').click()

  await expect(
    page.locator(SELECTORS.login),
    'login did not take effect: the menu still offers Login'
  ).toHaveText(/logout/i)
}

/** Log in at the API and return the bearer token. */
async function apiLogin(request, creds = CREDENTIALS) {
  const res = await request.post('/auth/jwt/login', {
    form: { username: creds.username, password: creds.password },
  })
  expect(res.status(), 'API login failed').toBe(200)
  const body = await res.json()
  return `${body.token_type} ${body.access_token}`
}

const test = base.extend({
  /** A page with an authenticated session already established. */
  authedPage: async ({ page }, use) => {
    await login(page)
    await use(page)
  },

  /** A bearer token for direct API assertions.
   *
   * Worker-scoped: one login per worker, not one per test.
   *
   * Per-test login meant roughly a hundred logins across eight parallel
   * workers, and the dev server is a single uvicorn process running with
   * `--reload`. It dropped connections under that -- `socket hang up` on
   * POST /auth/jwt/login, about one full-suite run in four, surfacing as
   * whichever unlucky test happened to be logging in at the time. It reads as
   * a flaky app and is a load pattern the suite creates for itself.
   *
   * Not a fix for the server's concurrency, which is a real question for a
   * production stack and out of scope here; it stops the suite manufacturing
   * the problem. `test_e2e.yml` already disables --reload for a related
   * reason.
   */
  token: [
    async ({ browser }, use, workerInfo) => {
      const context = await request.newContext({
        baseURL: workerInfo.project.use.baseURL,
      })
      const bearer = await apiLogin(context)
      await use(bearer)
      await context.dispose()
    },
    { scope: 'worker' },
  ],
})

/**
 * Hold back what the page asks to run "as soon as possible" -- `setTimeout`
 * with no delay -- until `releaseTheRouter`.
 *
 * Among it is mithril's router reading the address back. `m.route.set` writes
 * the address at once and resolves the route it describes on that later tick,
 * and until then `m.route.param()` answers with the route from before. On a
 * busy page a click or a redraw lands in between now and then; held, one
 * lands there every time a test makes one.
 */
const holdTheRouter = page =>
  page.evaluate(() => {
    const later = window.setTimeout
    const held = []
    window.setTimeout = (run, delay, ...args) => {
      if (delay !== undefined) return later(run, delay, ...args)
      held.push(() => run(...args))
      return 0
    }
    window.releaseTheRouter = () => {
      window.setTimeout = later
      for (const run of held.splice(0)) run()
    }
  })

const releaseTheRouter = page => page.evaluate(() => window.releaseTheRouter())

module.exports = {
  test,
  expect,
  login,
  apiLogin,
  holdTheRouter,
  releaseTheRouter,
  CREDENTIALS,
  SELECTORS,
}

/** The shared media fixture, created once in global-setup.js.
 *
 * Named here so specs and setup cannot disagree about it. Specs must not
 * create it themselves: eight workers doing check-then-create produced three
 * copies and broke a spec that counts project rows.
 */
module.exports.MEDIA_PROJECT = 'Tool test'

/** A template preview's query, with its `data` JSON unpacked into parameters. */
module.exports.templateQuery = url => {
  const query = new URLSearchParams(url.searchParams)
  const data = query.get('data')
  query.delete('data')
  for (const [key, value] of Object.entries(data ? JSON.parse(data) : {})) {
    if (value != null) query.set(key, typeof value === 'object' ? JSON.stringify(value) : String(value))
  }
  return query
}

/** The panels the workspace has, by registry id (src/layout/registry.js). */
module.exports.PANEL_IDS = [
  'projects',
  'media',
  'viewer',
  'timeline',
  'template',
  'render',
  'deliver',
  'captions',
  'transcript',
]

/** Where a viewer's arrangement of the workspace is kept (src/layout/saved_layout.js). */
module.exports.LAYOUT_KEY = 'alfred.layout.v1'
