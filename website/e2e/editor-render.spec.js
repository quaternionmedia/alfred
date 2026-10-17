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

test.describe('the toolbar Render button', () => {
  test('sends the Render stage request, in the body', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * It sent `?project=&width=&height=` and a body of bare clips. The route
     * reads only the body, so every render from this button came out at the
     * 1920x1080 default with no project -- and with no starts, stacked.
     */
    const project = await projectNamed(request, token, MEDIA_PROJECT)
    const saved = project.render_settings || {}
    const width = saved.width || 1920
    const height = saved.height || 1080
    const sent = await captureRenders(authedPage)
    await authedPage.route(
      url => url.pathname === `/project/${project._id}/settings`,
      route => route.fulfill({ json: project })
    )

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    const button = authedPage.locator('#render-timeline')
    // The button has no fields, so its title says what it will render at.
    await expect(button).toHaveAttribute('title', `Render this timeline at ${width}×${height}`)
    await button.click()

    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(authedPage).toHaveURL(new RegExp(`project=${project._id}`))
    expect(sent).toHaveLength(1)
    const toolbar = sent[0]
    expect([...toolbar.url.searchParams.keys()], 'settings in the query string').toEqual([])
    expect(toolbar.body).toMatchObject({
      name: project.name,
      project: project.name,
      project_id: project._id,
      width,
      height,
    })
    let at = 0
    expect(starts(toolbar.body)).toEqual(
      project.edl.clips.map(c => {
        const start = at
        at += c.duration
        return start
      })
    )
    expect(toolbar.body.duration).toBe(at)

    // And it is the same request the Render stage sends for this timeline.
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(2)
    expect(sent[1].body).toEqual(toolbar.body)
  })
})

test.describe('a form-driven project', () => {
  /**
   * A project with fields and logic renders from a form on the Render stage:
   * the logic compiles the form into clips. Those clips are layered on
   * purpose -- here a colour field from 0 and a title over it from 1s -- so
   * they keep their own starts, and a clip with none leaves with an explicit
   * 0 rather than relying on the renderer's default.
   *
   * The form also sent ffmpeg flags of its own and a quality of "web" or
   * "TV"; the server now picks the encoding from a named preset and refuses
   * client-supplied ffmpeg parameters, so this asserts neither is sent.
   */
  let project

  test.beforeEach(async ({ request, token }) => {
    const created = await request.post('/project', {
      headers: { Authorization: token },
      data: {
        name: `form render ${test.info().workerIndex}-${test.info().repeatEachIndex}`,
        fields: [
          { type: 'Text', attrs: { name: 'headline', text: 'Headline' } },
          { type: 'Selector', attrs: { name: 'duration', text: 'Duration' }, children: ['4'] },
        ],
        logic: {
          merge: [
            {
              eachKey: {
                type: 'template',
                name: 'makeColor',
                duration: 4,
                data: { preserve: { color: '#101820' } },
              },
            },
            {
              eachKey: {
                type: 'template',
                name: 'title',
                duration: 2,
                start: 1,
                data: { eachKey: { text: { var: 'headline' } } },
              },
            },
          ],
        },
      },
    })
    expect(created.status(), await created.text()).toBeLessThan(400)
    project = await created.json()
  })

  test.afterEach(async ({ request, token }) => {
    if (project) {
      await request.delete(`/project/${project._id}`, { headers: { Authorization: token } })
    }
  })

  test('renders its logic layered, with a preset and no ffmpeg flags', async ({
    authedPage,
  }) => {
    const sent = await captureRenders(authedPage)
    const previews = []
    await authedPage.route(
      url => url.pathname === '/preview/',
      async route => {
        previews.push(route.request().postDataJSON())
        await route.fulfill({ json: 'data/none.jpg' })
      }
    )

    await authedPage.goto(`/#!/?project=${project._id}&stage=render`)
    const form = authedPage.locator('#template_form')
    await expect(form).toBeVisible()
    await form.locator('input[name="headline"]').fill('Hello from the form')
    await form.locator('select[name="quality"]').selectOption('high')

    // By name: the buttons are inputs whose label mithril sets as the
    // `value` property, which a `[value=...]` selector cannot see.
    await form.locator('input[name="preview"]').click()
    await expect.poll(() => previews.length).toBe(1)
    expect(previews[0].edl.clips.map(c => c.start)).toEqual([0, 1])

    await form.locator('input[name="save"]').click()
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(authedPage).toHaveURL(new RegExp(`project=${project._id}`))

    expect(sent).toHaveLength(1)
    const { body } = sent[0]
    expect(body).not.toHaveProperty('ffmpeg_params')
    expect(body).not.toHaveProperty('bitrate')
    expect(body.quality).toBe('high')
    expect(body.project_id).toBe(project._id)
    // Layered as the logic placed them: the colour from 0 -- explicitly now
    // -- and the title over it from 1s.
    expect(starts(body)).toEqual([0, 1])
    expect(body.edl.clips[1].data.text).toBe('Hello from the form')
    expect(body.duration).toBe(4)
    expect(body.edl.duration).toBe(4)
  })
})
