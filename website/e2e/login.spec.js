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
})
