const { test, expect, login, CREDENTIALS, SELECTORS } = require('./fixtures')

test.describe('login UI', () => {
  test('shows an error for an invalid password', async ({ page }) => {
    await page.goto('/')
    await page.locator(SELECTORS.login).click()

    await page.locator('#username').fill(CREDENTIALS.username)
    await page.locator('#password').fill('wrong-password')
    await page.locator('#submit').click()

    // alertify renders the failure notice
    await expect(page.locator('.ajs-message')).toBeVisible()

    // and the session is still anonymous. The Cypress equivalent asserted
    // only that the path was still '/', which is also true of a *successful*
    // login, so it could not distinguish the two outcomes.
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })

  test('logs in with valid credentials', async ({ page }) => {
    await login(page)
    await expect(page.locator(SELECTORS.login)).toHaveText(/logout/i)
  })

  test('logs back out', async ({ authedPage }) => {
    await authedPage.locator(SELECTORS.login).click()
    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/login/i)
  })

  test('leaves a protected view anonymous for a visitor', async ({ page }) => {
    await page.goto('/#!/projects')
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })

  test('a deep link survives logging in', async ({ page }) => {
    /**
     * The login screen carries the route to come back to, and a route with a
     * query in it -- a stage, a project -- came back as nothing. mithril
     * decodes the whole hash before splitting off the query, so
     * `redirect=/?stage=render` split on its second `=` and the value read
     * as empty; logging in landed on `/` every time.
     */
    await page.goto('/#!/?stage=render')
    await expect(page).toHaveURL(/#!\/login\?redirect=/)

    await page.locator('#username').fill(CREDENTIALS.username)
    await page.locator('#password').fill(CREDENTIALS.password)
    await page.locator('#submit').click()

    await expect(page).toHaveURL(/#!\/\?stage=render/)
  })
})

/** Fill the form, press register, and accept the first-name prompt.
 *
 * The prompt's OK button is found by its role and label: index.js gives
 * alertify's OK button its own classes (`defaults.theme.ok`), so alertify's
 * `.ajs-ok` is not on it.
 */
async function register(page, email, password) {
  await page.goto('/#!/login')
  await page.locator('#username').fill(email)
  await page.locator('#password').fill(password)
  await page.locator('#register').click()
  await page.locator('.ajs-dialog').getByRole('button', { name: /^ok$/i }).click()
}

test.describe('registering', () => {
  test('a server that does not take registrations says so', async ({ page }) => {
    /**
     * Registration is closed by default in production. Every refusal used to
     * read "error regestering", which invites somebody to keep trying a thing
     * nothing they type can fix. The server's own reason is shown instead.
     *
     * Answered here rather than by a closed server, because this suite
     * registers its own user and needs registration open to do it.
     */
    await page.route('**/auth/register', route =>
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail:
            'Registration is closed on this server. Ask an administrator for an account.',
        }),
      })
    )

    await register(page, 'nobody@example.com', 'a long enough password')

    await expect(page.locator('.ajs-message')).toContainText(/registration is closed/i)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })

  test('an address that already has an account says so', async ({ page }) => {
    await register(page, CREDENTIALS.username, CREDENTIALS.password)

    await expect(page.locator('.ajs-message')).toContainText(/already has an account/i)
  })

  test('the address of the development login cannot be registered', async ({ page }) => {
    /**
     * The auth bypass acts as dev@example.com, and that account owns the
     * seeded projects. It is made the first time the bypass runs, so on a
     * server where it never had, whoever registered the address owned them.
     * The server refuses it in any case, and says why.
     */
    await register(page, 'Dev@Example.com', 'a long enough password')

    await expect(page.locator('.ajs-message')).toContainText(/development login/i)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })
})
