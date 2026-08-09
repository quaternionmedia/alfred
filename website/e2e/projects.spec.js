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

  test('the edit action stays inside the flow', async ({ authedPage }) => {
    /**
     * These used to leave for #!/editor and #!/form -- routes with no stage
     * rail and no timeline, reachable from this list and unable to get back to
     * it. Both now select the project and land on the stage that holds what
     * they used to show.
     */
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.projectrow').first().getByTitle(/edit the template/i).click()

    await expect(authedPage).toHaveURL(/project=[0-9a-f]{24}/)
    await expect(authedPage).toHaveURL(/stage=source/)
    await expect(authedPage.locator('.stagerail .stage')).toHaveCount(4)
  })

  test('the create-video action stays inside the flow', async ({ authedPage }) => {
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.projectrow').first().getByTitle(/create a video/i).click()

    await expect(authedPage).toHaveURL(/project=[0-9a-f]{24}/)
    await expect(authedPage).toHaveURL(/stage=render/)
    await expect(authedPage.locator('.stagerail .stage')).toHaveCount(4)
  })

  test('a project id naming nothing says so and offers a way out', async ({
    authedPage,
  }) => {
    // A stale bookmark or a hand-edited link. Silently ignoring it leaves the
    // stages looking empty for no stated reason.
    await authedPage.goto('/#!/?project=nonexistent&stage=source')
    await expect(authedPage.locator('#unknown-project')).toBeVisible()

    await authedPage.locator('#unknown-project button').click()
    await expect(authedPage).not.toHaveURL(/project=nonexistent/)
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

  test('choosing material puts it on the timeline', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: putting footage on the timeline
     *
     * The Material list named every file on the server and offered no way to
     * use any of them -- each entry was an `<li>` with text in it. The only
     * route from "I have footage" to "it is on the timeline" was to find the
     * bin on the editor stage and drag, an affordance with no visible cue,
     * unreachable from the keyboard, and on a different stage from the list
     * that told you the footage existed.
     */
    await request.post('/demo/media', { headers: { Authorization: token } })
    await authedPage.goto('/#!/?stage=source')

    const choice = authedPage.locator('.mediachoice').first()
    await expect(choice).toBeVisible()

    const before = await authedPage.locator('#timeline .clip').count()
    await choice.click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(before + 1)
  })

  test('material added without a project survives the next redraw', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The timeline reloaded its project on every redraw, and the guard meant
     * to stop that compared a raw `undefined` against a normalised `null`. So
     * with no project selected the comparison never matched, the branch that
     * clears the clip list ran about sixty times a second, and anything added
     * to the timeline was erased before it could be drawn.
     *
     * A count taken immediately would have passed throughout. This one waits.
     */
    await request.post('/demo/media', { headers: { Authorization: token } })
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.mediachoice').first().click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    await authedPage.waitForTimeout(1200)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)
  })

  test('a chosen clip is what the viewer shows', async ({
    authedPage,
    request,
    token,
  }) => {
    // Adding something and having the viewer keep showing something else
    // reads as the click not having worked.
    await request.post('/demo/media', { headers: { Authorization: token } })
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.mediachoice').first().click()

    // A blob URL, not the path: /videos needs the session token, so the
    // element is handed an object URL fetched with it rather than a `src` the
    // browser would request anonymously and be refused.
    await expect(authedPage.locator('video.preview')).toHaveAttribute(
      'src',
      /^blob:/
    )
  })

  test('an anonymous visitor is sent to login', async ({ page }) => {
    // Assert the redirect, not the absence of rows: an unauthenticated visitor
    // never reaches the panel, so a count of zero says nothing.
    await page.goto('/#!/projects')
    await expect(page).toHaveURL(/#!\/login/)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
  })
})
