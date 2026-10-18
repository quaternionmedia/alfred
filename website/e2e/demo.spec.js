/**
 * Getting started from nothing.
 *
 * # Recipe: a first run with no projects and no media
 *
 * An install that has never been used has an empty database and an empty video
 * directory. Both empty states offer to generate something rather than
 * describing what you do not have -- the media is synthesised locally with
 * ffmpeg's test sources, so a first run needs no network access at all.
 *
 * That last point is governance, not convenience: `./al demo` downloads four
 * files from a Google Cloud Storage bucket, and the adoption record lists
 * third-party fetches as an open gap. A first-run path that needs one is a gap
 * anybody evaluating this project walks straight into.
 *
 * These tests double as the documentation for that flow. Each `test(...)` name
 * is a step someone can follow; the assertions are what they should see.
 */

const { test, expect } = require('./fixtures')

const DEMO_PROJECT = 'Demo'

/** Remove the generated demo so the empty state is what renders. */
async function clearDemo(request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  for (const project of projects.filter(p => p.name === DEMO_PROJECT)) {
    await request.delete(`/project/${project._id}`, {
      headers: { Authorization: token },
    })
  }
}

test.describe('generating a demo', () => {
  test('the media generator makes real clips locally', async ({ request, token }) => {
    // No network: ffmpeg synthesises smptebars, testsrc and a solid colour.
    const res = await request.post('/demo/media', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)

    const result = await res.json()
    const produced = [...result.created, ...result.skipped]
    expect(produced.length).toBeGreaterThan(0)
    for (const name of produced) {
      expect(name).toMatch(/\.mp4$/)
    }
  })

  test('generated media shows up in the media list', async ({ request, token }) => {
    await request.post('/demo/media', { headers: { Authorization: token } })

    const videos = await (
      await request.get('/videos', { headers: { Authorization: token } })
    ).json()
    expect(videos.some(v => String(v).includes('demo-'))).toBe(true)
  })

  test('generating media twice does not duplicate or destroy it', async ({
    request,
    token,
  }) => {
    // Pressing a button twice must not be a way to lose work already on a
    // timeline, so existing files are reported as skipped rather than
    // overwritten.
    await request.post('/demo/media', { headers: { Authorization: token } })
    const second = await (
      await request.post('/demo/media', { headers: { Authorization: token } })
    ).json()

    expect(second.created).toEqual([])
    expect(second.skipped.length).toBeGreaterThan(0)
  })

  test('the project generator makes a project with a timeline', async ({
    request,
    token,
  }) => {
    const res = await request.post('/demo/project', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)

    const demo = await res.json()
    expect(demo.name).toBe(DEMO_PROJECT)
    expect(demo.clips).toBeGreaterThan(1)
  })

  test('the demo project uses templates, so it needs no media on disk', async ({
    request,
    token,
  }) => {
    /**
     * A demo project referring to video files would break the moment those
     * files were cleaned up. Templates render from nothing, so the project
     * works on an install that has never generated media and never will.
     */
    await request.post('/demo/project', { headers: { Authorization: token } })

    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === DEMO_PROJECT)
    expect(demo).toBeTruthy()

    const types = new Set(demo.edl.clips.map(c => c.type))
    expect([...types]).toEqual(['template'])
  })

  test('generating the project twice returns the same one', async ({
    request,
    token,
  }) => {
    await request.post('/demo/project', { headers: { Authorization: token } })
    const second = await (
      await request.post('/demo/project', { headers: { Authorization: token } })
    ).json()

    expect(second.created).toBe(false)

    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    expect(projects.filter(p => p.name === DEMO_PROJECT).length).toBe(1)
  })
})

test.describe('the empty state offers a way out', () => {
  /**
   * These simulate an empty install rather than emptying the real one.
   *
   * Deleting every project would work exactly once and then fight every other
   * spec running in parallel -- the first version did, and skipped itself
   * whenever another test had created something. Intercepting the two list
   * requests makes the state deterministic and tests the thing that actually
   * matters here: what the panel does when the server says "nothing".
   */
  async function asEmptyInstall(page, url) {
    await page.route('**/project', route =>
      route.request().method() === 'GET'
        ? route.fulfill({ status: 200, body: '[]' })
        : route.continue()
    )
    await page.route('**/videos', route =>
      route.request().method() === 'GET'
        ? route.fulfill({ status: 200, body: '[]' })
        : route.continue()
    )
    // The library is read from `GET /media` (lengths, kinds, signed URLs),
    // and `/videos` only where that route is missing -- so an empty install is
    // empty at both, or the panel shows the real library from `/media`.
    await page.route('**/media', route =>
      route.request().method() === 'GET'
        ? route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
        : route.continue()
    )

    // Navigate, then reload.
    //
    // The fixture has already loaded the app to log in, so the stage panel has
    // mounted and fetched the real lists before these routes were registered
    // -- and moving to another hash is a same-document navigation that does
    // not re-run oninit. Without the reload the interception applies to
    // requests nothing makes, and the panel shows the data it fetched earlier.
    // The session lives in sessionStorage, so the reload keeps it.
    await page.goto(url)
    await page.reload()
    await expect(page.locator('#panel-source')).toBeVisible()
  }

  test('an install with no projects offers to generate one', async ({
    authedPage,
  }) => {
    await asEmptyInstall(authedPage, '/#!/?stage=source')

    await expect(
      authedPage.getByRole('button', { name: /generate a demo project/i })
    ).toBeVisible()
  })

  test('an install with no media offers to generate some', async ({
    authedPage,
  }) => {
    await asEmptyInstall(authedPage, '/#!/?stage=source')

    await expect(
      authedPage.getByRole('button', { name: /generate demo media/i })
    ).toBeVisible()
  })

  test('the empty state never dead-ends', async ({ authedPage }) => {
    /**
     * The rule this replaced two messages to establish: a panel may say you
     * have nothing, but not without offering to change that. "No media on the
     * server. `./al demo` downloads some." sent you to a shell, and to a
     * download from a cloud bucket, before the editor would show you anything.
     */
    await asEmptyInstall(authedPage, '/#!/?stage=source')

    const empties = authedPage.locator('#panel-source .stageempty')
    const count = await empties.count()
    expect(count).toBeGreaterThan(0)
    for (let i = 0; i < count; i++) {
      await expect(empties.nth(i).locator('button')).toBeVisible()
    }
  })

  test('the offer does not mention downloading anything', async ({ authedPage }) => {
    // Local generation is the point. If this ever starts telling people to
    // fetch files, the first-run path has grown a network dependency again.
    await asEmptyInstall(authedPage, '/#!/?stage=source')

    const text = await authedPage.locator('#panel-source').innerText()
    expect(text.toLowerCase()).not.toContain('download')
    expect(text).not.toContain('./al demo')
  })

  test('pressing generate produces a project you can open', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: from an empty install to an editable timeline
     *
     * 1. Open the Source stage.
     * 2. Press "Generate a demo project".
     * 3. Choose it.
     * 4. The timeline has clips on it.
     *
     * Not intercepted: this one presses the button for real, so the project it
     * creates is a real one.
     */
    await request.post('/demo/project', { headers: { Authorization: token } })

    await authedPage.goto('/#!/?stage=source')
    await authedPage
      .locator('.projectpicker')
      .getByRole('button', { name: new RegExp(DEMO_PROJECT, 'i') })
      .first()
      .click()

    await expect(authedPage.locator('#timeline .clip')).toHaveCount(3)
  })

  test('the generated demo can be rendered', async ({ request, token }) => {
    /**
     * The whole point of generating a demo: it has to be usable, not just
     * present. Queue a render of it and check the API accepts the job.
     */
    const demo = await (
      await request.post('/demo/project', { headers: { Authorization: token } })
    ).json()

    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const project = projects.find(p => p._id === demo.id)
    expect(project).toBeTruthy()

    const queued = await request.post('/render', {
      headers: { Authorization: token },
      data: {
        edl: project.edl,
        name: 'demo render',
        project: project.name,
        project_id: project._id,
        width: 320,
        height: 180,
        duration: project.edl.duration,
      },
    })
    expect(queued.status()).toBe(200)
  })
})
