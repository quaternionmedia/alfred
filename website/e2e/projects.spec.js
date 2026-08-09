const { test, expect, SELECTORS } = require('./fixtures')

/**
 * Choosing a project.
 *
 * # Recipe: finding and opening a project
 *
 * There were two project lists: a table at `#!/projects` and the picker on the
 * Source stage, each fetching `/project` separately and rendering it
 * differently. Two components with their own state for one list means they
 * disagree — generating a project on one did not reach the other, and neither
 * knew when a selection changed.
 *
 * The Source stage is the only one now. `#!/projects` redirects to it, so old
 * bookmarks and older documentation still land somewhere sensible, and the
 * selector carries what the table offered: the edit-template and create-video
 * actions, plus the clip count, duration and last render size the table could
 * not show.
 */
test.describe('the project selector', () => {
  test('the old projects URL redirects into the flow', async ({ authedPage }) => {
    // Kept as a redirect rather than deleted: this is the URL the menu used
    // and the one anyone has bookmarked.
    await authedPage.goto('/#!/projects')
    await expect(authedPage).toHaveURL(/stage=source/)
    await expect(authedPage.locator('#panel-source')).toBeVisible()
  })

  test('one row per project, named as the API names them', async ({
    authedPage,
    request,
    token,
  }) => {
    const res = await request.get('/project', { headers: { Authorization: token } })
    expect(res.status()).toBe(200)
    const projects = await res.json()
    test.skip(projects.length === 0, 'no projects in this environment')

    await authedPage.goto('/#!/?stage=source')
    const rows = authedPage.locator('.projectrow')

    // Polled against a fresh count: other specs create projects while this
    // runs, so a count captured before the page loaded is stale by the time
    // the DOM is measured.
    await expect
      .poll(async () => {
        const current = await request.get('/project', {
          headers: { Authorization: token },
        })
        return (await current.json()).length === (await rows.count())
      })
      .toBe(true)

    for (const project of projects) {
      await expect(
        authedPage.getByRole('button', { name: new RegExp(project.name, 'i') }).first()
      ).toBeVisible()
    }
  })

  test('each row shows what is on the project, not just its name', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The table showed a name and two icons. Whether a project had anything on
     * its timeline — the thing that decides if opening it is worthwhile — was
     * not visible until you opened it.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const withClips = projects.find(p => ((p.edl || {}).clips || []).length)
    test.skip(!withClips, 'no project with a timeline in this environment')

    await authedPage.goto('/#!/?stage=source')
    const row = authedPage
      .locator('.projectrow')
      .filter({ hasText: withClips.name })
      .first()

    const clips = withClips.edl.clips.length
    await expect(row.locator('.projectclips')).toHaveText(
      new RegExp(`${clips} clip`)
    )
  })

  test('each row offers an edit and a create-video action', async ({
    authedPage,
  }) => {
    // Carried over from the table, which was the only place these lived.
    await authedPage.goto('/#!/?stage=source')
    const row = authedPage.locator('.projectrow').first()

    await expect(row.getByTitle(/edit the template/i)).toBeVisible()
    await expect(row.getByTitle(/create a video/i)).toBeVisible()
  })

  test('the edit action routes to the template editor for that project', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.projectrow').first().getByTitle(/edit the template/i).click()
    await expect(authedPage).toHaveURL(/#!\/editor\?project=[0-9a-f]{24}/)
  })

  test('the create-video action routes to the form for that project', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.projectrow').first().getByTitle(/create a video/i).click()
    await expect(authedPage).toHaveURL(/#!\/form\?project=[0-9a-f]{24}/)
  })

  test('choosing a project opens it on the timeline', async ({
    authedPage,
    request,
    token,
  }) => {
    // The card itself is the choice; the icons beside it go elsewhere. That
    // distinction is the reason they are separate buttons.
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const withClips = projects.find(p => ((p.edl || {}).clips || []).length)
    test.skip(!withClips, 'no project with a timeline')

    await authedPage.goto('/#!/?stage=source')
    await authedPage
      .locator('.projectrow')
      .filter({ hasText: withClips.name })
      .first()
      .locator('.projectchoice')
      .click()

    await expect(authedPage).toHaveURL(new RegExp(`project=${withClips._id}`))
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      withClips.edl.clips.length
    )
  })

  test('the filter narrows the list without losing anything', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A filter rather than pagination: the list is small enough to render
     * whole, and typing a name beats scrolling for one. It appears only when
     * there are enough projects to be worth filtering.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    test.skip(projects.length <= 3, 'too few projects for the filter to appear')

    await authedPage.goto('/#!/?stage=source')
    const filter = authedPage.locator('#project-filter')
    await expect(filter).toBeVisible()

    const target = projects[0].name
    await filter.fill(target)
    await expect(authedPage.locator('.projectrow')).toHaveCount(
      projects.filter(p => (p.name || '').toLowerCase().includes(target.toLowerCase()))
        .length
    )

    await filter.fill('')
    await expect(authedPage.locator('.projectrow')).toHaveCount(projects.length)
  })

  test('an anonymous visitor is sent to login', async ({ page }) => {
    // Assert the redirect, not the absence of rows: an unauthenticated visitor
    // never reaches the panel, so a count of zero says nothing.
    await page.goto('/#!/projects')
    await expect(page).toHaveURL(/#!\/login/)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })
})
