const { test, expect, SELECTORS } = require('./fixtures')

/**
 * Projects view.
 *
 * The Cypress suite had one live test here named "adds new project" which
 * asserted only that `.projects` was visible and added nothing. Five further
 * cases -- opening a project, previewing it, saving a render -- were
 * commented out. That name is not carried over: a test named for behavior it
 * does not exercise is worse than no test, because it reports coverage that
 * does not exist.
 *
 * These assert against the projects the API actually returns. The app seeds
 * three demo projects into an empty database on startup, so a fresh stack has
 * content to check; the tests read the expected set from the API rather than
 * hardcoding it, so they survive a different seed.
 */
test.describe('projects', () => {
  test('renders the projects list for an authenticated user', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/projects')
    await expect(authedPage.locator('.projects')).toBeVisible()
    await expect(
      authedPage.getByRole('heading', { name: 'Projects' })
    ).toBeVisible()
  })

  test('table header names the three columns', async ({ authedPage }) => {
    await authedPage.goto('/#!/projects')
    const head = authedPage.locator('table.projTableHead')
    await expect(head).toBeVisible()
    for (const column of ['Name', 'Edit Template', 'Create New Video']) {
      await expect(head).toContainText(column)
    }
  })

  test('one row per project, named as the API names them', async ({
    authedPage,
    request,
    token,
  }) => {
    const res = await request.get('/project', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)
    const projects = await res.json()
    test.skip(projects.length === 0, 'no projects seeded in this environment')

    await authedPage.goto('/#!/projects')
    const rows = authedPage.locator('table.projTable tr')
    await expect(rows).toHaveCount(projects.length)

    for (const project of projects) {
      await expect(
        authedPage.locator('table.projTable td', { hasText: project.name })
      ).toBeVisible()
    }
  })

  test('each row offers an edit and a create-video action', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/projects')
    const firstRow = authedPage.locator('table.projTable tr').first()

    await expect(firstRow.getByText('edit', { exact: true })).toBeVisible()
    await expect(
      firstRow.getByText('video_call', { exact: true })
    ).toBeVisible()
  })

  test('the edit action routes to the template editor for that project', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/projects')
    await authedPage
      .locator('table.projTable tr')
      .first()
      .getByText('edit', { exact: true })
      .click()

    await expect(authedPage).toHaveURL(/#!\/editor\?project=[0-9a-f]{24}/)
  })

  test('the create-video action routes to the form for that project', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/projects')
    await authedPage
      .locator('table.projTable tr')
      .first()
      .getByText('video_call', { exact: true })
      .click()

    await expect(authedPage).toHaveURL(/#!\/form\?project=[0-9a-f]{24}/)
  })

  test('an anonymous visitor gets no project rows', async ({ page }) => {
    await page.goto('/#!/projects')
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
    await expect(page.locator('table.projTable tr')).toHaveCount(0)
  })
})
