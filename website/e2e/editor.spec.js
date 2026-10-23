/**
 * The timeline editor, with a project open.
 *
 * None of this was testable before: the Project model had no `edl` field, so
 * every project opened an empty timeline, and there was no way to tell a
 * broken editor from an empty one. A seeded "Timeline demo" project is what
 * makes these assertions possible.
 *
 * The suite finds that project through the API rather than hardcoding an id,
 * so it survives a reseed.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

const DEMO = 'Timeline demo'

async function demoProject(request, token) {
  const res = await request.get('/project', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  const projects = await res.json()
  return projects.find(p => p.name === DEMO)
}

test.describe('timeline editor', () => {
  test('the demo project is seeded with a timeline', async ({ request, token }) => {
    /** "Timeline demo" exists and has more than one clip to edit. */
    const demo = await demoProject(request, token)
    expect(demo, `no project named "${DEMO}"`).toBeTruthy()
    expect(demo.edl.clips.length).toBeGreaterThan(1)
  })

  test('the timeline renders one element per clip', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Counted against the API rather than a literal: the seed can change
     * without this test needing to.
     */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    await authedPage.goto(`/#!/otto?project=${demo._id}`)
    const timeline = authedPage.locator('#timeline')
    await expect(timeline).toBeVisible()
    await expect(timeline.locator('.clip')).toHaveCount(demo.edl.clips.length)
  })

  test('each timeline clip is named after its template', async ({
    authedPage,
    request,
    token,
  }) => {
    /** A clip on the timeline carries its template's name. */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    await authedPage.goto(`/#!/otto?project=${demo._id}`)
    for (const clip of demo.edl.clips) {
      await expect(
        authedPage.locator(`#timeline .clip[name="${clip.name}"]`).first()
      ).toBeVisible()
    }
  })

  test('the media bin lists the templates the API offers', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The bin was permanently empty: it asked for /otto/templates, which has
     * never existed, and the rejection was unhandled so nothing showed.
     */
    const res = await request.get('/templates', { headers: { Authorization: token } })
    expect(res.status()).toBe(200)
    const templates = await res.json()
    expect(templates.length).toBeGreaterThan(0)

    await authedPage.goto('/#!/otto')
    const bin = authedPage.locator('#bin')
    await expect(bin).toBeVisible()

    // Polled rather than asserted once. The bin fills from two requests --
    // templates and videos -- and mithril redraws between them, so a one-shot
    // count caught an intermediate state about one run in three. That looked
    // like a flaky app and was a flaky assertion.
    await expect
      .poll(() => bin.locator('.clip.template').count(), {
        message: 'the bin never listed every template the API offers',
      })
      .toBe(templates.length)
  })

  test('the old editor URL lands on the project stage', async ({ authedPage }) => {
    /**
     * #!/editor was a route with no stage rail and no timeline. Its content
     * is a property of a project, so it lives beside the project you
     * selected.
     */
    await authedPage.goto('/#!/editor')
    await expect(authedPage).toHaveURL(/stage=source/)
    await expect(authedPage.locator('.stagerail .stage')).toHaveCount(4)
  })

  test('a selected project offers its template', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The project's form logic and fields, beside the project on the Source
     * stage. Collapsed by default: most visits here are to pick a project,
     * not to inspect one.
     */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=source`)
    const toggle = authedPage.locator('#template-toggle')
    await expect(toggle).toBeVisible()

    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(authedPage.locator('.templatebody')).toBeVisible()
  })

  test('a clip added while the project is loading is kept', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The project's clips arrive asynchronously, and the response used to
     * replace the whole timeline -- so a clip added before it landed vanished
     * when it did, and Save then found nothing to save. That was the save
     * test in tools.spec.js failing on most runs. The response is held back
     * here so the order is certain rather than lucky.
     */
    const project = (
      await (await request.get('/project', { headers: { Authorization: token } })).json()
    ).find(p => p.name === MEDIA_PROJECT)
    expect(project).toBeTruthy()

    let release
    const held = new Promise(resolve => (release = resolve))
    await authedPage.route(
      url => url.pathname === `/project/${project._id}`,
      async route => {
        await held
        await route.fallback()
      }
    )

    await authedPage.goto(`/#!/?project=${project._id}&stage=source`)
    await authedPage.locator('.mediachoice').first().click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    release()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length + 1
    )
    // The project's clips first, then the addition.
    const names = await authedPage
      .locator('#timeline .clip')
      .evaluateAll(nodes => nodes.map(n => n.getAttribute('name')))
    expect(names.slice(0, -1)).toEqual(project.edl.clips.map(c => c.name))
  })

  test('a project that does not exist is asked for once, not in a loop', async ({
    authedPage,
  }) => {
    /**
     * A failed load forgot the id, the answer redrew, and the redraw asked
     * again: an unknown id in the URL was requested for as long as the page
     * stayed open.
     */
    const missing = 'deadbeefdeadbeefdeadbeef'
    let asked = 0
    authedPage.on('request', req => {
      if (new URL(req.url()).pathname === `/project/${missing}`) asked++
    })

    await authedPage.goto(`/#!/?project=${missing}&stage=edit`)
    await authedPage.waitForTimeout(2500)
    expect(asked).toBe(1)
  })

  test('opening the editor makes no failing requests', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The regression guard for this whole session's frontend work.
     *
     * Opening /otto used to produce four failures per visit: a 404 for
     * /[object Object] from a broken asset import, a 401 for /videos because
     * the bin used a request helper that sends no token, a 404 for
     * /otto/templates which never existed, and a 500 for /project/undefined.
     * None of them failed a test, because none of them threw.
     */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    const failures = []
    authedPage.on('requestfinished', async req => {
      try {
        const res = await req.response()
        if (res && res.status() >= 400) {
          failures.push(`${res.status()} ${req.method()} ${new URL(req.url()).pathname}`)
        }
      } catch (e) {
        // request objects can go away mid-navigation; nothing to record
      }
    })

    await authedPage.goto(`/#!/otto?project=${demo._id}`)
    await expect(authedPage.locator('#timeline .clip').first()).toBeVisible()
    await authedPage.waitForTimeout(1500)

    expect(failures, `failing requests while opening the editor:\n${failures.join('\n')}`)
      .toEqual([])
  })
})
