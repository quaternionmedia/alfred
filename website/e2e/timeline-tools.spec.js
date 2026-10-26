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

const { test, expect, MEDIA_PROJECT, templateQuery } = require('./fixtures')

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

/**
 * What the timeline holds, by way of the request a render would send.
 *
 * The toolbar's Render moves on to the Deliver stage, whose list takes the
 * room the timeline had; the page is brought back to Edit, so a test can go
 * on editing.
 */
async function sentTimeline(page, sent) {
  const before = sent.length
  await page.locator('#render-timeline').click()
  await expect.poll(() => sent.length).toBe(before + 1)
  await expect(page).toHaveURL(/stage=deliver/)
  await page.locator('#stage-edit').click()
  return sent[before].edl
}

const basename = name => String(name).split('/').pop()

/**
 * Serve `GET /media` for the library's real files, each `lengths[file]`
 * seconds long, or a minute.
 *
 * An edit stops at the end of a clip's file, so a test that drags a clip
 * longer, or slides the window it shows, says how long the file is rather
 * than depending on what the demo media happens to measure -- or on whether
 * the server measures anything at all.
 */
async function serveMedia(page, request, token, lengths = {}) {
  const names = await (
    await request.get('/videos', { headers: { Authorization: token } })
  ).json()
  await page.route(
    url => url.pathname === '/media',
    route =>
      route.fulfill({
        json: names.map(name => ({
          name,
          kind: 'video',
          duration: basename(name) in lengths ? lengths[basename(name)] : 60,
          width: 320,
          height: 180,
          fps: 24,
          size: 1000,
          url: null,
        })),
      })
  )
}

/**
 * Open the shared media project on the Edit stage.
 *
 * With `clips`, the project is served holding those instead, so a test can
 * start from the timeline it needs without writing to the shared fixture.
 * With `lengths`, the media list is served too (see serveMedia) and the page
 * reloaded: the library is read once per page load, and the fixture's login
 * already read it.
 */
async function openMediaProject(page, request, token, { clips, lengths } = {}) {
  const project = await mediaProject(request, token)
  // Keeps the shared fixture as it is when the toolbar's render remembers.
  await page.route(
    url => url.pathname === `/project/${project._id}/settings`,
    route => route.fulfill({ json: project })
  )
  const opened = clips ? { ...project, edl: { ...project.edl, clips } } : project
  if (clips) {
    await page.route(
      url => url.pathname === `/project/${project._id}`,
      route =>
        route.request().method() === 'GET' ? route.fulfill({ json: opened }) : route.fallback()
    )
  }
  if (lengths) await serveMedia(page, request, token, lengths)
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  if (lengths) await page.reload()
  await expect(page.locator('#timeline .clip')).toHaveCount(opened.edl.clips.length)
  return opened
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
     * gesture -- and the clips after it move along. (Its file is served as a
     * minute long, so the end of the file is not what stops it.)
     */
    const project = await openMediaProject(authedPage, request, token, { lengths: {} })
    const sent = await captureRenders(authedPage)
    const first = project.edl.clips[0]

    await authedPage.locator('#TTools [data-tool="trim"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    // On screen first, as onClip below does: a drag is pointer events at a
    // point, and on a phone the clip can be scrolled out of its region.
    await clip.scrollIntoViewIfNeeded()
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
    await openMediaProject(authedPage, request, token, { lengths: {} })
    await authedPage.locator('#TTools [data-tool="trim"]').click()

    const clip = authedPage.locator('#timeline .clip').first()
    await clip.scrollIntoViewIfNeeded()
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

    await authedPage.locator('#timeline .clip').nth(1).scrollIntoViewIfNeeded()
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
    // On screen, or the swipe lands on nothing and proves nothing.
    await authedPage.locator('#timeline .clip').nth(1).scrollIntoViewIfNeeded()
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

  test('a template clip becomes two halves of one animation, edited separately', async ({
    authedPage,
  }) => {
    /**
     * Two clips of the same template, each with its own copy of the
     * settings. The second carries on where the first stopped: it starts in
     * the template where the cut was (its in-point) and ends where the
     * original did (its out-point), so its animation continues rather than
     * starting over -- in the viewer, and in the render.
     */
    const sent = await captureRenders(authedPage)
    const frames = []
    authedPage.on('request', req => {
      const url = new URL(req.url())
      if (url.pathname === '/preview/template/title') frames.push(templateQuery(url))
    })
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

    // The viewer shows the second half from where the cut was in the
    // template, not from the template's start.
    await expect
      .poll(() => frames.filter(p => p.get('text') === 'Second half').map(p => Number(p.get('t'))))
      .toContainEqual(expect.closeTo(2.5, 1))

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    const [a, b] = sent[0].edl.clips
    expect(a).toMatchObject({ name: 'title', start: 0, data: { text: 'Your text here' } })
    expect(b).toMatchObject({ name: 'title', data: { text: 'Second half' } })
    expect(a.duration).toBeCloseTo(2.5, 1)
    expect(b.start).toBeCloseTo(a.duration, 3)
    expect(a.duration + b.duration).toBeCloseTo(5, 3)
    // The first half is the template from its start, as it was.
    expect(a).not.toHaveProperty('inpoint')
    // The second plays the template from the cut to the original's end.
    expect(b.inpoint).toBeCloseTo(a.duration, 3)
    expect(b.outpoint).toBeCloseTo(5, 3)
    expect(b.outpoint - b.inpoint).toBeCloseTo(b.duration, 3)
  })

  test("a continuing half keeps its window when its length changes", async ({
    authedPage,
  }) => {
    /**
     * otto plays a clip with an out-point from its in-point to its out-point
     * and does not read `duration`. So a length typed beside the viewer has
     * to move the out-point too, or the render would ignore it.
     */
    const sent = await captureRenders(authedPage)
    await authedPage.goto('/#!/?stage=edit')
    await authedPage.locator('#bin .binclip[data-bin-name="title"] .binadd').click()
    await authedPage.locator('#TTools [data-tool="cut"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    await clip.click({ position: { x: box.width * 0.4, y: box.height / 2 } })
    await expect(authedPage.locator('#template-params h4')).toContainText('clip 2')

    await authedPage.locator('#param-duration').fill('1.5')
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    const [, b] = sent[0].edl.clips
    expect(b.inpoint).toBeCloseTo(2, 1)
    expect(b.duration).toBe(1.5)
    expect(b.outpoint).toBeCloseTo(b.inpoint + 1.5, 3)
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

/** The library's name for the demo file whose name contains `part`. */
async function libraryFile(request, token, part) {
  const names = await (
    await request.get('/videos', { headers: { Authorization: token } })
  ).json()
  const name = names.find(n => n.includes(part))
  expect(name, `no ${part} in the media library; global-setup.js generates it`).toBeTruthy()
  return name
}

/** A clip of a library file playing `from` to `to` seconds of it. */
const media = (name, from, to) => ({
  type: 'video',
  name,
  inpoint: from,
  outpoint: to,
  duration: to - from,
})

const colour = seconds => ({
  type: 'template',
  name: 'makeColor',
  duration: seconds,
  data: { color: '#f2aa4c' },
})

/** Drag from `from` to `to` (page coordinates) with the mouse. */
async function mouseDrag(page, from, to) {
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(to.x, to.y, { steps: 10 })
  await page.mouse.up()
}

/**
 * Where the pointer should be, `along` a clip (0..1) -- with the clip on
 * screen. Pointer events go to whatever is at the point, so a clip scrolled
 * out of its region, under the footer, would not receive them.
 */
async function onClip(page, index, along = 0.5) {
  const clip = page.locator('#timeline .clip').nth(index)
  await clip.scrollIntoViewIfNeeded()
  const box = await clip.boundingBox()
  return { x: box.x + box.width * along, y: box.y + box.height / 2, box }
}

const timings = edl => edl.clips.map(c => [c.start, c.inpoint, c.outpoint, c.duration])
const FIELDS = ['start', 'inpoint', 'outpoint', 'duration']

/**
 * Each clip's `[start, inpoint, outpoint, duration]`, to a twentieth of a
 * second -- a drag moves whole pixels, and a pixel is a fiftieth of a second
 * at the default zoom. `undefined` where a clip has no such field.
 */
function expectTimings(edl, expected) {
  const actual = timings(edl)
  expect(actual.length, `clips: ${JSON.stringify(actual)}`).toBe(expected.length)
  actual.forEach((row, i) =>
    row.forEach((value, j) => {
      const what = `clip ${i + 1} ${FIELDS[j]} in ${JSON.stringify(actual)}`
      if (expected[i][j] === undefined) expect(value, what).toBeUndefined()
      else expect(value, what).toBeCloseTo(expected[i][j], 1)
    })
  )
}

// Tall enough that the timeline is not squeezed under the footer: these are
// drags, and a drag cannot start on something scrolled out of sight.
const ROOM = { width: 1280, height: 1000 }

test.describe('slip', () => {
  /**
   * # Recipe: choosing which part of a clip plays
   *
   * Choose **Slip** and drag a clip: it keeps its length and its place, and
   * the part of its file it shows moves under it. The picture follows the
   * pointer, as in other editors -- drag right to bring in earlier material,
   * left for later -- stopping at the start and the end of the file.
   */
  test.use({ viewport: ROOM })

  test('by mouse, the window moves along the file and nothing else does', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 2, 5), colour(2)],
      lengths: { [basename(bars)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slip"]').click()

    // 3 seconds drawn across the clip's width: a second is a third of it.
    const at = await onClip(authedPage, 0)
    const second = at.box.width / 3
    await mouseDrag(authedPage, at, { x: at.x - second, y: at.y })

    const edl = await sentTimeline(authedPage, sent)
    expectTimings(edl, [
      // Later material, by a second: in 3, out 6, still three seconds long...
      [0, 3, 6, 3],
      // ...and the next clip has not moved.
      [3, undefined, undefined, 2],
    ])
    expect(edl.duration).toBe(5)
  })

  test('it stops at the start and at the end of the file', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 2, 5), colour(2)],
      lengths: { [basename(bars)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slip"]').click()

    // Far to the right: as early as the file goes.
    let at = await onClip(authedPage, 0)
    await mouseDrag(authedPage, at, { x: at.x + at.box.width * 4, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 0, 3, 3],
      [3, undefined, undefined, 2],
    ])

    // Far to the left: as late as the file goes, ending at its end.
    at = await onClip(authedPage, 0)
    await mouseDrag(authedPage, at, { x: at.x - at.box.width * 6, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 7, 10, 3],
      [3, undefined, undefined, 2],
    ])
  })

  test('a template slips through its animation', async ({ authedPage, request, token }) => {
    /**
     * A template is drawn on demand from its own second 0, so it can show
     * any stretch of its animation -- but nothing before its start.
     */
    await openMediaProject(authedPage, request, token, { clips: [colour(4), colour(2)] })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slip"]').click()

    const at = await onClip(authedPage, 0)
    const second = at.box.width / 4
    await mouseDrag(authedPage, at, { x: at.x - 1.5 * second, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 1.5, 5.5, 4],
      [4, undefined, undefined, 2],
    ])
  })

  test('a clip showing the whole of its file says there is nothing to slip', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), colour(2)],
      lengths: { [basename(bars)]: 3 },
    })
    await authedPage.locator('#TTools [data-tool="slip"]').click()
    const at = await onClip(authedPage, 0)
    await mouseDrag(authedPage, at, { x: at.x - 40, y: at.y })
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: /nothing to slip/i }).first()
    ).toBeVisible()
  })
})

test.describe('slide', () => {
  /**
   * # Recipe: moving a clip between its neighbours
   *
   * Choose **Slide** and drag a clip along the timeline. It keeps what it
   * shows; its neighbours give and take the time -- the clip before it ends
   * later or sooner, the clip after it starts later or sooner in its file --
   * so the timeline keeps its length.
   */
  test.use({ viewport: ROOM })

  test('by mouse, the neighbours give and take the time', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    const card = await libraryFile(request, token, 'demo-testcard')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), colour(2), media(card, 1, 4)],
      lengths: { [basename(bars)]: 10, [basename(card)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slide"]').click()

    const at = await onClip(authedPage, 1)
    const second = at.box.width / 2
    await mouseDrag(authedPage, at, { x: at.x + second, y: at.y })

    const edl = await sentTimeline(authedPage, sent)
    expectTimings(edl, [
      // The clip before it ends a second later in its file...
      [0, 0, 4, 4],
      // ...the slid clip is unchanged, a second later on the timeline...
      [4, undefined, undefined, 2],
      // ...and the clip after it starts a second later in its file.
      [6, 2, 4, 2],
    ])
    expect(edl.duration).toBe(8)
  })

  test('the first clip has nothing before it to slide against, and says so', async ({
    authedPage,
    request,
    token,
  }) => {
    await openMediaProject(authedPage, request, token)
    await authedPage.locator('#TTools [data-tool="slide"]').click()
    const at = await onClip(authedPage, 0)
    await mouseDrag(authedPage, at, { x: at.x + 40, y: at.y })
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: /none before it/i }).first()
    ).toBeVisible()
  })
})

test.describe('dual roller', () => {
  /**
   * # Recipe: moving a cut
   *
   * Choose the **dual roller** and drag near a cut: the cut moves, the clip
   * before it ending where the clip after it now starts in its file. Pressed
   * on a clip's first half, the roller takes the cut at its start; on its
   * second half, the cut at its end.
   */
  test.use({ viewport: ROOM })

  test('by mouse, one clip ends where the next now starts', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    const card = await libraryFile(request, token, 'demo-testcard')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), media(card, 1, 4)],
      lengths: { [basename(bars)]: 10, [basename(card)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="dual roller"]').click()

    // On the first clip's second half: the cut at its end.
    const at = await onClip(authedPage, 0, 0.8)
    const second = at.box.width / 3
    await mouseDrag(authedPage, at, { x: at.x - second, y: at.y })

    const edl = await sentTimeline(authedPage, sent)
    expectTimings(edl, [
      [0, 0, 2, 2],
      [2, 0, 4, 4],
    ])
    expect(edl.duration).toBe(6)
  })

  test('the cut moves only as far as both clips allow', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Rolled right, the second clip gives up all but a tenth of a second:
     * the shortest a clip may be. Rolled left, the second clip can start no
     * earlier than its file does.
     */
    const bars = await libraryFile(request, token, 'demo-bars')
    const card = await libraryFile(request, token, 'demo-testcard')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), media(card, 1, 4)],
      lengths: { [basename(bars)]: 10, [basename(card)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="dual roller"]').click()

    // On the second clip's first half: the cut at its start.
    let at = await onClip(authedPage, 1, 0.2)
    await mouseDrag(authedPage, at, { x: at.x + at.box.width * 3, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 0, 5.9, 5.9],
      [5.9, 3.9, 4, 0.1],
    ])

    // Back the other way, past where the second clip's file begins.
    at = await onClip(authedPage, 0, 0.9)
    await mouseDrag(authedPage, at, { x: at.x - at.box.width, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 0, 2, 2],
      [2, 0, 4, 4],
    ])
  })

  test('a single clip has no cut to roll, and says so', async ({
    authedPage,
    request,
    token,
  }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    await openMediaProject(authedPage, request, token, { clips: [media(bars, 0, 3)] })
    await authedPage.locator('#TTools [data-tool="dual roller"]').click()
    const at = await onClip(authedPage, 0)
    await mouseDrag(authedPage, at, { x: at.x + 40, y: at.y })
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: /no clip on the other side/i }).first()
    ).toBeVisible()
  })
})

test.describe('slip, slide and roll by touch', () => {
  test.use({ hasTouch: true, viewport: ROOM })

  test('a finger slips a clip', async ({ authedPage, request, token }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 2, 5), colour(2)],
      lengths: { [basename(bars)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slip"]').click()

    const at = await onClip(authedPage, 0)
    await touchDrag(authedPage, at, { x: at.x + at.box.width / 3, y: at.y })
    // Earlier material, by a second.
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 1, 4, 3],
      [3, undefined, undefined, 2],
    ])
  })

  test('a finger slides a clip', async ({ authedPage, request, token }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    const card = await libraryFile(request, token, 'demo-testcard')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), colour(2), media(card, 1, 4)],
      lengths: { [basename(bars)]: 10, [basename(card)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="slide"]').click()

    const at = await onClip(authedPage, 1)
    await touchDrag(authedPage, at, { x: at.x - at.box.width / 2, y: at.y })
    // A second earlier: the clip before it gives a second up, and the clip
    // after it starts a second earlier in its file.
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 0, 2, 2],
      [2, undefined, undefined, 2],
      [4, 0, 4, 4],
    ])
  })

  test('a finger rolls a cut', async ({ authedPage, request, token }) => {
    const bars = await libraryFile(request, token, 'demo-bars')
    const card = await libraryFile(request, token, 'demo-testcard')
    await openMediaProject(authedPage, request, token, {
      clips: [media(bars, 0, 3), media(card, 1, 4)],
      lengths: { [basename(bars)]: 10, [basename(card)]: 10 },
    })
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#TTools [data-tool="dual roller"]').click()

    const at = await onClip(authedPage, 1, 0.2)
    await touchDrag(authedPage, at, { x: at.x + at.box.width / 3, y: at.y })
    expectTimings(await sentTimeline(authedPage, sent), [
      [0, 0, 4, 4],
      [4, 2, 4, 2],
    ])
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

test.describe('zoom', () => {
  test('its buttons and its bar sit side by side, none drawn over another', async ({
    authedPage,
  }) => {
    // Mutation: zoom in `position: absolute; right: 0` (Scale.js) -- fails on a phone.
    await authedPage.goto('/')
    // Icons are words until the font loads; measure after.
    await authedPage.evaluate(() => document.fonts.ready)
    const bar = authedPage.locator('.zoombar')
    const box = await bar.boundingBox()
    const out = await bar.locator('i', { hasText: 'zoom_out' }).boundingBox()
    const into = await bar.locator('i', { hasText: 'zoom_in' }).boundingBox()
    for (const [name, b] of [['zoom out', out], ['zoom in', into]]) {
      expect(b.x, `${name} starts outside the zoom bar`).toBeGreaterThanOrEqual(box.x - 1)
      expect(b.x + b.width, `${name} ends outside the zoom bar`).toBeLessThanOrEqual(
        box.x + box.width + 1
      )
    }
    // A wrapped row sits a button lower; settling layout moves a pixel or two.
    expect(Math.abs(out.y - into.y), 'the buttons share a row').toBeLessThan(out.height / 2)

    const scale = authedPage.locator('#scale')
    if (await scale.isVisible()) {
      const s = await scale.boundingBox()
      expect(out.x + out.width, 'the bar starts under zoom out').toBeLessThanOrEqual(s.x)
      expect(s.x + s.width, 'the bar runs under zoom in').toBeLessThanOrEqual(into.x)
    } else {
      expect(out.x + out.width, 'zoom in is drawn over zoom out').toBeLessThanOrEqual(into.x)
    }
  })
})
