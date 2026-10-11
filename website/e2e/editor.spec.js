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

const { test, expect } = require('./fixtures')

const DEMO = 'Timeline demo'

async function demoProject(request, token) {
  const res = await request.get('/project', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  const projects = await res.json()
  return projects.find(p => p.name === DEMO)
}

test.describe('timeline editor', () => {
  test('the demo project is seeded with a timeline', async ({ request, token }) => {
    const demo = await demoProject(request, token)
    expect(demo, `no project named "${DEMO}"`).toBeTruthy()
    expect(demo.edl.clips.length).toBeGreaterThan(1)
  })

  test('the timeline renders one element per clip', async ({
    authedPage,
    request,
    token,
  }) => {
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    await authedPage.goto(`/#!/otto?project=${demo._id}`)
    const timeline = authedPage.locator('#timeline')
    await expect(timeline).toBeVisible()
    // Count from the API rather than a literal: the seed can change without
    // this test needing to.
    await expect(timeline.locator('.clip')).toHaveCount(demo.edl.clips.length)
  })

  test('each timeline clip is named after its template', async ({
    authedPage,
    request,
    token,
  }) => {
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
    const res = await request.get('/templates', { headers: { Authorization: token } })
    expect(res.status()).toBe(200)
    const templates = await res.json()
    expect(templates.length).toBeGreaterThan(0)

    await authedPage.goto('/#!/otto')
    const bin = authedPage.locator('#bin')
    await expect(bin).toBeVisible()

    // The bin was permanently empty: it asked for /otto/templates, which has
    // never existed, and the rejection was unhandled so nothing showed.
    //
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
    // #!/editor was a route with no stage rail and no timeline. Its content is
    // a property of a project, so it lives beside the project you selected.
    await authedPage.goto('/#!/editor')
    await expect(authedPage).toHaveURL(/stage=source/)
    await expect(authedPage.locator('.stagerail .stage')).toHaveCount(4)
  })

  test('a selected project offers its template', async ({
    authedPage,
    request,
    token,
  }) => {
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded in this environment')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=source`)
    const toggle = authedPage.locator('#template-toggle')
    await expect(toggle).toBeVisible()

    // Collapsed by default: most visits here are to pick a project, not to
    // inspect one.
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(authedPage.locator('.templatebody')).toBeVisible()
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
