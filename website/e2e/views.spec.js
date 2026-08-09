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
  test('the renders view is now the deliver stage', async ({ authedPage }) => {
    // `#!/renders` was a standalone table listing data the flow also listed.
    // It redirects into the stage that owns that list.
    await authedPage.goto('/#!/renders')
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()
  })

  test('the documentation links are always to hand', async ({ authedPage }) => {
    // #!/documents was a whole view, outside the editor, for two links. They
    // are in the footer now, so reading them costs no navigation.
    await authedPage.goto('/')
    await expect(authedPage.locator('footer a.docLink')).toHaveCount(2)

    await authedPage.goto('/#!/documents')
    await expect(authedPage).toHaveURL(/stage=source/)
  })

  test('home view loads', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator(SELECTORS.login)).toBeVisible()
  })

  test('each view renders without an uncaught page error', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * This test existed and passed while the Source stage threw on every
     * render. It walked the routes that take no parameters, and the throw was
     * in the branch that only runs once a project is selected -- so the panel
     * produced no DOM at all, and nothing here went near it. Four other specs
     * failed on the symptoms (an empty timeline, a missing disclosure, a
     * missing warning) and none named the cause.
     *
     * So the walk now includes the states a parameter puts the app into: a
     * real project, and an id matching nothing.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const selected = (projects.find(p => ((p.edl || {}).clips || []).length) ||
      projects[0] || {})._id

    const routes = ['/#!/projects', '/#!/renders', '/#!/documents']
    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      routes.push(`/#!/?stage=${stage}`)
      if (selected) routes.push(`/#!/?stage=${stage}&project=${selected}`)
    }
    routes.push('/#!/?stage=source&project=nonexistent')

    // Collected per route, so a failure names the one that threw rather than
    // reporting that something, somewhere, did.
    const failures = []
    for (const route of routes) {
      const errors = watchForPageErrors(authedPage)
      await authedPage.goto(route)
      await authedPage.waitForTimeout(250)
      if (errors.length) failures.push(`${route}: ${errors[0]}`)
    }

    expect(failures, `uncaught errors:\n${failures.join('\n')}`).toEqual([])
  })

  test('an unknown route does not leave a blank page', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/no-such-route')
    // Whatever the router does with an unknown hash, the shell must survive:
    // the menu is still there and the document is not empty.
    await expect(authedPage.locator(SELECTORS.stages)).toHaveCount(4)
    const text = await authedPage.locator('body').innerText()
    expect(text.trim().length).toBeGreaterThan(0)
  })

  test('a reload keeps the session', async ({ authedPage }) => {
    // This test previously asserted the opposite, and said so: the app held
    // its JWT in a module-level object, so a reload logged you out, and the
    // note read "anyone who later moves auth into storage should see this test
    // change". This is that change. The token is now kept in sessionStorage
    // and restored before routing.
    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/logout/i)

    await authedPage.reload()

    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/logout/i)
  })

  test('logging out survives a reload too', async ({ authedPage }) => {
    // The other half, and the one worth having: a stored token that outlived
    // logout would be a session nobody could end.
    await authedPage.goto('/#!/logout')
    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/login/i)

    await authedPage.reload()

    await expect(authedPage.locator(SELECTORS.login)).toHaveText(/login/i)
  })

  test('a session does not leak into a fresh browser context', async ({
    browser,
  }) => {
    // sessionStorage is per-tab, so a new context starts logged out. Worth
    // pinning: switching to localStorage to "fix" something would silently
    // widen the token's lifetime and this is what would notice.
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
    await context.close()
  })
})
