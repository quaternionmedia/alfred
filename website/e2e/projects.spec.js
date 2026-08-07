const { test, expect } = require('./fixtures')

/**
 * Projects view.
 *
 * The Cypress suite had one live test here named "adds new project" which
 * asserted only that `.projects` was visible and added nothing. Five further
 * cases -- opening a project, previewing it, saving a render -- were
 * commented out. The name is not carried over, because a test named for
 * behavior it does not exercise is worse than no test: it reports coverage
 * that does not exist.
 */
test.describe('projects', () => {
  test('renders the projects list for an authenticated user', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/projects')
    await expect(authedPage.locator('.projects')).toBeVisible()
  })

  test('project list reflects what the API returns', async ({
    authedPage,
    request,
    token,
  }) => {
    const res = await request.get('/project', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)
    const projects = await res.json()

    await authedPage.goto('/#!/projects')
    await expect(authedPage.locator('.projects')).toBeVisible()

    // Only assert the correspondence when the API has something to show;
    // an empty database is a valid state and not a test failure.
    test.skip(projects.length === 0, 'no projects seeded in this environment')
    await expect(authedPage.locator('.project')).toHaveCount(projects.length)
  })
})
