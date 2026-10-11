const { test, expect, SELECTORS } = require('./fixtures')

/**
 * The remaining top-level views.
 *
 * Basic coverage only: each view reaches its route, renders its own heading
 * rather than the previous view's, and does not throw in the browser. That
 * last check is worth more than it looks -- a mithril view that raises during
 * render leaves the page half-drawn without failing any request, so nothing
 * else in this suite would notice.
 */

/** Fail the test if the page logs an uncaught error while it is open. */
function watchForPageErrors(page) {
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  return errors
}

test.describe('views', () => {
  test('renders view loads with its heading', async ({ authedPage }) => {
    await authedPage.goto('/#!/renders')
    await expect(
      authedPage.getByRole('heading', { name: 'Renders' })
    ).toBeVisible()
  })

  test('documents view loads with its heading', async ({ authedPage }) => {
    await authedPage.goto('/#!/documents')
    await expect(
      authedPage.getByRole('heading', { name: 'Documents' })
    ).toBeVisible()
  })

  test('home view loads', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator(SELECTORS.login)).toBeVisible()
  })

  test('each view renders without an uncaught page error', async ({
    authedPage,
  }) => {
    const errors = watchForPageErrors(authedPage)

    for (const route of ['/#!/projects', '/#!/renders', '/#!/documents']) {
      await authedPage.goto(route)
      await authedPage.waitForTimeout(250)
    }

    expect(errors, `uncaught errors: ${errors.join(' | ')}`).toEqual([])
  })

  test('an unknown route does not leave a blank page', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/no-such-route')
    // Whatever the router does with an unknown hash, the shell must survive:
    // the menu is still there and the document is not empty.
    await expect(authedPage.locator(SELECTORS.projects)).toBeVisible()
    const text = await authedPage.locator('body').innerText()
    expect(text.trim().length).toBeGreaterThan(0)
  })

  test('a reload ends the session', async ({ authedPage }) => {
    // Not a defect to fix here, a property to pin. The app holds its JWT in a
    // module-level object (src/User.js), so nothing survives a reload. Anyone
    // who later moves auth into storage should see this test change.
    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/logout/i)

    await authedPage.reload()

    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/login/i)
  })
})
