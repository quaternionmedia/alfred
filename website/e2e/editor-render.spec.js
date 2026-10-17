/**
 * What the editor sends when it asks for a render.
 *
 * The editor plays its timeline as one track, each clip starting where the
 * previous one ends. The renderer places clips by an explicit `start` and
 * layers overlaps, treating a missing `start` as 0. The editor used to send
 * clips with no `start` at all, so three five-second clips rendered stacked at
 * second 0 -- five seconds of overlap, then ten of black -- while the preview
 * played them one after another.
 *
 * These read the request the page actually sends (intercepted and answered
 * here, so nothing is queued) rather than trusting the code that builds it.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

const FAKE_RENDER_ID = 'abcdefabcdefabcdefabcdef'

/**
 * Answer the page's `POST /render` without queueing anything, and keep what it
 * sent.
 *
 * Matched on the path alone, so a request that smuggles its settings into the
 * query string -- which is what the toolbar button used to do -- is caught
 * rather than missed.
 */
async function captureRenders(page) {
  const sent = []
  await page.route(
    url => url.pathname === '/render',
    async route => {
      const request = route.request()
      if (request.method() !== 'POST') return route.fallback()
      sent.push({ url: new URL(request.url()), body: request.postDataJSON() })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(FAKE_RENDER_ID),
      })
    }
  )
  return sent
}

async function projectNamed(request, token, name) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === name)
  expect(project, `${name} is missing; global-setup.js creates it`).toBeTruthy()
  return project
}

const starts = body => body.edl.clips.map(c => c.start)
const durations = body => body.edl.clips.map(c => c.duration)

test.describe('the render request places every clip', () => {
  test('three clips added in the editor render end to end, not stacked', async ({
    authedPage,
  }) => {
    /**
     * # Recipe: what "render" sends
     *
     * The exact case from the bug report: three five-second clips. They must
     * arrive at 0, 5 and 10 seconds, with a total of 15 -- not all at 0.
     */
    const sent = await captureRenders(authedPage)

    await authedPage.goto('/#!/?stage=source')
    const media = authedPage.locator('.mediachoice').first()
    await expect(media).toBeVisible()
    for (let n = 1; n <= 3; n++) {
      await media.click()
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(n)
    }

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()

    expect(sent).toHaveLength(1)
    const { body } = sent[0]
    expect(starts(body)).toEqual([0, 5, 10])
    expect(durations(body)).toEqual([5, 5, 5])
    expect(body.edl.duration).toBe(15)
    expect(body.duration).toBe(15)
    // The view's bookkeeping stays in the view.
    for (const clip of body.edl.clips) expect(clip).not.toHaveProperty('i')
  })

  test('a start stored on a clip is replaced by its place on the timeline', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A saved `start` records where a clip was when it was saved. Reordering,
     * trimming or cutting moves it, so the request must be computed from the
     * timeline as it stands and never echo the stored value. Served here with
     * every stored start wrong, to prove the editor ignores them.
     */
    const demo = await projectNamed(request, token, 'Timeline demo')
    const doctored = {
      ...demo,
      edl: {
        ...demo.edl,
        clips: demo.edl.clips.map(c => ({ ...c, start: 99 })),
      },
    }
    await authedPage.route(
      url => url.pathname === `/project/${demo._id}`,
      route =>
        route.request().method() === 'GET'
          ? route.fulfill({ json: doctored })
          : route.fallback()
    )
    const sent = await captureRenders(authedPage)

    await authedPage.goto(`/#!/?project=${demo._id}&stage=render`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )
    await authedPage.locator('#queue-render').click()
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()

    expect(sent).toHaveLength(1)
    const { body } = sent[0]
    const expected = []
    let at = 0
    for (const clip of demo.edl.clips) {
      expected.push(at)
      at += clip.duration
    }
    expect(starts(body)).toEqual(expected)
    expect(body.edl.duration).toBe(at)
    expect(body.project).toBe(demo.name)
    expect(body.project_id).toBe(demo._id)
  })

  test('the size typed on the Render stage is the size requested', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The size inputs were uncontrolled, and mithril writes `value` back on
     * every redraw -- so a redraw between typing and clicking restored the
     * project's size. Forcing a redraw in between is the point of this test.
     */
    const project = await projectNamed(request, token, MEDIA_PROJECT)
    const sent = await captureRenders(authedPage)
    // The stage remembers the size on the project afterwards. Answered here
    // too, so this test does not rewrite a fixture other specs read.
    const remembered = []
    await authedPage.route(
      url => url.pathname === `/project/${project._id}/settings`,
      async route => {
        const patch = route.request().postDataJSON()
        remembered.push(patch)
        await route.fulfill({ json: { ...project, ...patch } })
      }
    )

    await authedPage.goto(`/#!/?project=${project._id}&stage=render`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await authedPage.locator('#render-width').fill('320')
    await authedPage.locator('#render-height').fill('180')
    // Anything that redraws will do; a stage round trip redraws twice.
    await authedPage.locator('#stage-edit').click()
    await authedPage.locator('#stage-render').click()
    await expect(authedPage.locator('#render-width')).toHaveValue('320')

    await authedPage.locator('#queue-render').click()
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()

    expect(sent).toHaveLength(1)
    expect(sent[0].body.width).toBe(320)
    expect(sent[0].body.height).toBe(180)
    expect([...sent[0].url.searchParams.keys()]).toEqual([])
    await expect
      .poll(() => remembered)
      .toEqual([{ render_settings: { width: 320, height: 180 } }])
  })
})
