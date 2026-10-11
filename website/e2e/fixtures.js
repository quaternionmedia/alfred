const { test: base, expect } = require('@playwright/test')
const { CREDENTIALS } = require('./credentials')

/**
 * Log in through the UI and assert it worked.
 *
 * Playwright's usual shortcut -- log in once via the API, save `storageState`,
 * reuse it -- is not available here. The app keeps its JWT in a module-level
 * object (`User` in `src/User.js`); nothing is written to localStorage or a
 * cookie, so there is no persisted credential to seed. A reload logs the user
 * out. The Cypress suite's `auth.js` tried exactly that shortcut and is
 * commented out in its entirety, which is consistent with it never having
 * worked.
 *
 * The success signal is the menu link's *text*, not its presence. The link is
 * rendered unconditionally and only swaps between "Login" and "Logout"
 * (`src/Menu.js`), so asserting it is visible -- as the Cypress suite did --
 * cannot fail in either state.
 *
 * Note the selector is `a.loginLink`, not `#login-link`. The app renders both
 * a nav bar and a menu bar from the same component set, so five ids are
 * emitted twice each on every page: home-link, projects-link, renders-link,
 * documents-link and login-link. Duplicate ids are invalid HTML, and
 * `#login-link` is genuinely ambiguous. `SELECTORS` below resolves each to
 * exactly one element; see e2e/README.md.
 */
const SELECTORS = {
  login: 'a.loginLink',
  projects: '.menuLinks a#projects-link',
  renders: '.menuLinks a#renders-link',
  documents: '.menuLinks a#documents-link',
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

  /** A bearer token for direct API assertions. */
  token: async ({ request }, use) => {
    await use(await apiLogin(request))
  },
})

module.exports = { test, expect, login, apiLogin, CREDENTIALS, SELECTORS }
