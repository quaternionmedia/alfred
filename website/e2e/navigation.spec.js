const { test, expect, SELECTORS } = require('./fixtures')

/**
 * Navigation and routing.
 *
 * Replaces the useful half of the Cypress suite's `window.js`. The rest of
 * that file tested the browser rather than the app -- that `localStorage.
 * setItem` followed by `getItem` returns what was set, that `document` has a
 * width and a height, and one case that set the page background to purple and
 * asserted nothing. Those were copied from a Cypress demo repository and are
 * dropped rather than converted.
 *
 * Its navigation assertions are kept but repaired. They checked that
 * `#login-link`, `#projects-link` and `#renders-link` were visible after
 * going back and forward; all three are rendered unconditionally by
 * `src/Menu.js`, so those assertions held on every route and in both auth
 * states. These assert the URL instead.
 */
test.describe('navigation', () => {
  test('menu exposes the primary sections', async ({ page }) => {
    await page.goto('/')
    for (const key of ['projects', 'renders', 'documents']) {
      await expect(page.locator(SELECTORS[key])).toBeVisible()
    }
  })

  test('menu links change the route', async ({ authedPage }) => {
    await authedPage.locator(SELECTORS.projects).click()
    await expect(authedPage).toHaveURL(/stage=source/)

    await authedPage.locator(SELECTORS.renders).click()
    await expect(authedPage).toHaveURL(/stage=deliver/)
  })

  test('back and forward move between routes', async ({ authedPage }) => {
    await authedPage.locator(SELECTORS.projects).click()
    await expect(authedPage).toHaveURL(/stage=source/)

    await authedPage.locator(SELECTORS.renders).click()
    await expect(authedPage).toHaveURL(/stage=deliver/)

    await authedPage.goBack()
    await expect(authedPage).toHaveURL(/stage=source/)

    await authedPage.goForward()
    await expect(authedPage).toHaveURL(/stage=deliver/)
  })

  test('serves the SPA shell at the root', async ({ page }) => {
    const res = await page.goto('/')
    expect(res.status()).toBe(200)
    expect(res.headers()['content-type']).toContain('text/html')
    await expect(page).toHaveTitle(/alfred/i)
  })

  test('every element id is unique', async ({ authedPage }) => {
    /**
     * This was annotated `test.fail()` as a known defect: the header rendered
     * the same links twice, once as a drawer and once as a bar, emitting
     * home-link, projects-link, renders-link, documents-link and login-link
     * twice each -- and every clip repeated clipname, inpoint and outpoint, so
     * a page with 17 clips carried 52 duplicates.
     *
     * Both are fixed: the header renders one list and CSS decides whether it
     * is a drawer, and per-clip labels are classes. Invalid HTML either way,
     * and `#id` selectors silently address only the first match, which is a
     * trap for anything written against this page later.
     */
    await authedPage.goto('/')
    const duplicates = await authedPage.evaluate(() => {
      const counts = {}
      document.querySelectorAll('[id]').forEach(el => {
        counts[el.id] = (counts[el.id] || 0) + 1
      })
      return Object.entries(counts)
        .filter(([, n]) => n > 1)
        .map(([id, n]) => `${id} x${n}`)
    })

    expect(duplicates, `duplicate element ids: ${duplicates.join(', ')}`).toEqual([])
  })
})
