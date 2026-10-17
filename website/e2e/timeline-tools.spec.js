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
    /**
     * Grab a clip near its end and drag. The pointer is captured, so the
     * drag keeps arriving at the clip after leaving its edge -- the whole
     * gesture -- and the clips after it move along.
     */
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
    /**
     * A real touch drag, sent through the browser's input pipeline rather
     * than as synthetic events -- the kind a phone sends.
     */
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
    /**
     * With the time tool, a tap half way along the second clip puts the
     * playhead half way through it.
     */
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
    /**
     * The press that starts a scroll is not a choice of position: seeking on
     * press would jump the playhead every time someone scrolled.
     */
    await openMediaProject(authedPage, request, token)
    const second = await authedPage.locator('#timeline .clip').nth(1).boundingBox()
    const y = second.y + second.height / 2
    await touchDrag(authedPage, { x: second.x + second.width - 4, y }, { x: second.x - 60, y })

    await authedPage.waitForTimeout(300)
    expect(await seconds(authedPage)).toBe(0)
  })
})

test.describe('cut', () => {
  /**
   * # Recipe: cutting a clip in two
   *
   * Choose the scissors and press a clip where it should split: the playhead
   * goes there and the clip becomes two. Or put the playhead anywhere and
   * press S. Either half can then be trimmed, moved or deleted on its own.
   */

  test('a media clip becomes two windows onto its file that meet', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The first half keeps the clip's in-point and ends where the cut is;
     * the second starts in the file where the first ends and finishes where
     * the original did. Back to back they show what the original showed.
     */
    const project = await openMediaProject(authedPage, request, token)
    const sent = await captureRenders(authedPage)
    const [media, rest] = project.edl.clips
    expect(media.type).toBe('video')

    await authedPage.locator('#TTools [data-tool="cut"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    await clip.click({ position: { x: box.width * 0.4, y: box.height / 2 } })

    await expect(authedPage.locator('#timeline .clip')).toHaveCount(3)
    const edl = await sentTimeline(authedPage, sent)
    const [first, second, third] = edl.clips
    const at = media.duration * 0.4

    expect(first.name).toBe(media.name)
    expect(first.inpoint).toBe(media.inpoint)
    expect(first.duration).toBeCloseTo(at, 1)
    expect(first.outpoint).toBeCloseTo(media.inpoint + first.duration, 3)

    expect(second.name).toBe(media.name)
    // The second half starts in the file where the first ends...
    expect(second.inpoint).toBeCloseTo(first.outpoint, 3)
    // ...and ends where the original did.
    expect(second.outpoint).toBeCloseTo(media.inpoint + media.duration, 3)
    expect(first.duration + second.duration).toBeCloseTo(media.duration, 3)

    // On the timeline they are back to back, and nothing after them moved.
    expect(second.start).toBeCloseTo(first.duration, 3)
    expect(third.name).toBe(rest.name)
    expect(third.start).toBeCloseTo(media.duration, 3)
    expect(edl.duration).toBeCloseTo(media.duration + rest.duration, 3)

    // The playhead is at the cut.
    await expect.poll(() => seconds(authedPage)).toBeCloseTo(at, 1)
  })

  test('a template clip becomes two of the same template, edited separately', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A template has no in-point -- it is drawn fresh for its length -- so
     * it becomes two clips of the same template, each with its own copy of
     * the settings.
     */
    const sent = await captureRenders(authedPage)
    await authedPage.goto('/#!/?stage=edit')
    await authedPage.locator('#bin .binclip[data-bin-name="title"] .binadd').click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    await authedPage.locator('#TTools [data-tool="cut"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    await clip.click({ position: { x: box.width / 2, y: box.height / 2 } })
    await expect(authedPage.locator('#timeline .clip.template[name="title"]')).toHaveCount(2)

    // The playhead is on the second half, so that is the one the settings
    // beside the viewer belong to. Changing it leaves the first alone.
    await expect(authedPage.locator('#template-params h4')).toContainText('clip 2')
    await authedPage.locator('#param-text').fill('Second half')
    await expect(authedPage.locator('#timeline .clip').nth(1)).toHaveText('Second half')
    await expect(authedPage.locator('#timeline .clip').first()).toHaveText('Your text here')

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    const [a, b] = sent[0].edl.clips
    expect(a).toMatchObject({ name: 'title', start: 0, data: { text: 'Your text here' } })
    expect(b).toMatchObject({ name: 'title', data: { text: 'Second half' } })
    expect(a.duration).toBeCloseTo(2.5, 1)
    expect(b.start).toBeCloseTo(a.duration, 3)
    expect(a.duration + b.duration).toBeCloseTo(5, 3)
    // A template is drawn fresh for its length; it has no in-point to move.
    expect(b).not.toHaveProperty('inpoint')
  })

  test('S splits the clip under the playhead, whatever the tool', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Put the playhead anywhere -- here with the time tool, half way through
     * the first clip -- and press S.
     */
    await openMediaProject(authedPage, request, token)
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    await clip.click({ position: { x: box.width / 2, y: box.height / 2 } })
    await expect.poll(() => seconds(authedPage)).toBeGreaterThan(0)

    await authedPage.keyboard.press('s')
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(3)
  })

  test('a cut at the very edge of a clip says why it did nothing', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * At 0 the playhead is at the very start of the first clip, so a cut
     * there would leave nothing on one side. It is refused, and says so.
     */
    const project = await openMediaProject(authedPage, request, token)
    await authedPage.keyboard.press('s')
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: /too close/i }).first()
    ).toBeVisible()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
  })
})

test.describe('on a phone', () => {
  test('the page is laid out to standard, and can be zoomed', async ({ page }) => {
    /**
     * There was no doctype, so every browser laid the page out in quirks
     * mode; and the viewport carried `maximum-scale=1`, which stops a phone
     * from zooming -- the one tool someone who needs larger controls has.
     */
    await page.goto('/')
    expect(await page.evaluate(() => document.compatMode)).toBe('CSS1Compat')
    expect(await page.evaluate(() => document.doctype && document.doctype.name)).toBe('html')

    const viewport = await page.locator('meta[name="viewport"]').getAttribute('content')
    expect(viewport).toContain('width=device-width')
    expect(viewport).not.toMatch(/maximum-scale|user-scalable\s*=\s*(no|0)/i)
  })
})
