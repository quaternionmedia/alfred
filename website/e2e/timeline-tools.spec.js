/**
 * The timeline tools, by mouse and by touch.
 *
 * # Recipe: trimming and cutting
 *
 * Choose a tool beside the timeline. **Trim** (`[ ]`) drags a clip's end to
 * make it longer or shorter. **Time** (`|`) moves the playhead to where you
 * press. The README promises editing on mobile devices, and these work by
 * touch as well as by mouse: they listen for pointer events, which are one
 * stream for both. They listened for mouse events, which a finger does not
 * send while it moves, so on a phone trimming did nothing at all.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

async function mediaProject(request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()
  return project
}

/** Answer `POST /render` without queueing anything, and keep the bodies. */
async function captureRenders(page) {
  const sent = []
  await page.route(
    url => url.pathname === '/render',
    async route => {
      if (route.request().method() !== 'POST') return route.fallback()
      sent.push(route.request().postDataJSON())
      await route.fulfill({ json: 'abcdefabcdefabcdefabcdef' })
    }
  )
  return sent
}

/** What the timeline holds, by way of the request a render would send. */
async function sentTimeline(page, sent) {
  const before = sent.length
  await page.locator('#render-timeline').click()
  await expect.poll(() => sent.length).toBe(before + 1)
  return sent[before].edl
}

async function openMediaProject(page, request, token) {
  const project = await mediaProject(request, token)
  // Keeps the shared fixture as it is when the toolbar's render remembers.
  await page.route(
    url => url.pathname === `/project/${project._id}/settings`,
    route => route.fulfill({ json: project })
  )
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await expect(page.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
  return project
}

const seconds = async page => {
  const [m, s] = (await page.locator('.timecode').innerText()).split(':')
  return Number(m) * 60 + Number(s)
}

/** A real touch gesture, through the browser's input pipeline. */
async function touchDrag(page, from, to, steps = 12) {
  const client = await page.context().newCDPSession(page)
  const point = i => ({
    x: from.x + ((to.x - from.x) * i) / steps,
    y: from.y + ((to.y - from.y) * i) / steps,
  })
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [point(0)],
  })
  for (let i = 1; i <= steps; i++) {
    await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [point(i)] })
  }
  await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await client.detach()
}

test.describe('trim, by mouse', () => {
  test('dragging a clip past its own edge lengthens it, and its out-point', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await openMediaProject(authedPage, request, token)
    const sent = await captureRenders(authedPage)
    const first = project.edl.clips[0]

    await authedPage.locator('#TTools i[title="trim"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()

    // Grabbed near its end and dragged well past it, over the next clip: the
    // pointer is captured, so the drag keeps arriving at this one.
    await authedPage.mouse.move(box.x + box.width - 6, box.y + box.height / 2)
    await authedPage.mouse.down()
    await authedPage.mouse.move(box.x + box.width + 114, box.y + box.height / 2, { steps: 10 })
    await authedPage.mouse.up()

    await expect.poll(async () => (await clip.boundingBox()).width).toBeCloseTo(box.width + 120, -1)

    const edl = await sentTimeline(authedPage, sent)
    const grown = first.duration * ((box.width + 120) / box.width)
    expect(edl.clips[0].duration).toBeCloseTo(grown, 0)
    // The out-point moves with the length; it used to stay where it was.
    expect(edl.clips[0].outpoint).toBeCloseTo(edl.clips[0].inpoint + edl.clips[0].duration, 3)
    // And the next clip now starts where this one ends.
    expect(edl.clips[1].start).toBeCloseTo(edl.clips[0].duration, 3)
  })
})

test.describe('by touch', () => {
  test.use({ hasTouch: true })

  test('a finger can trim a clip', async ({ authedPage, request, token }) => {
    await openMediaProject(authedPage, request, token)
    await authedPage.locator('#TTools i[title="trim"]').click()

    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    const y = box.y + box.height / 2
    await touchDrag(authedPage, { x: box.x + box.width - 6, y }, { x: box.x + box.width + 94, y })

    await expect.poll(async () => (await clip.boundingBox()).width).toBeCloseTo(box.width + 100, -1)
  })

  test('a tap on a clip moves the playhead to that point of it', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await openMediaProject(authedPage, request, token)
    const [a, b] = project.edl.clips
    expect(await seconds(authedPage)).toBe(0)

    const second = await authedPage.locator('#timeline .clip').nth(1).boundingBox()
    await authedPage.touchscreen.tap(second.x + second.width / 2, second.y + second.height / 2)

    await expect.poll(() => seconds(authedPage)).toBeCloseTo(a.duration + b.duration / 2, 1)
  })

  test('a swipe across the timeline is a scroll, not a seek', async ({
    authedPage,
    request,
    token,
  }) => {
    // The press that starts a scroll is not a choice of position: seeking on
    // press would jump the playhead every time someone scrolled.
    await openMediaProject(authedPage, request, token)
    const second = await authedPage.locator('#timeline .clip').nth(1).boundingBox()
    const y = second.y + second.height / 2
    await touchDrag(authedPage, { x: second.x + second.width - 4, y }, { x: second.x - 60, y })

    await authedPage.waitForTimeout(300)
    expect(await seconds(authedPage)).toBe(0)
  })
})
