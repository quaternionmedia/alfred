/**
 * The timeline's lanes (src/lanes/Lanes.js): the ruler above the clips, and
 * the words, the sound, the effects and the cues under them, at one scale.
 *
 * # Recipe: reading the timeline
 *
 * Open a project on **Edit**. Above the clips a ruler counts the seconds;
 * under them the **Text** lane shows each word where it was said and each
 * caption where it is shown, the **Audio** lane the loudness of the sound,
 * the **FX** lane each clip's fades, and the **Cues** lane what has been
 * marked on the timeline -- the excerpts the harness proposes, and where each
 * stands. Press anywhere in a lane to put the playhead there; a word, a
 * caption or a cue takes it to its start. Zoom out and the words become marks,
 * then make way for the captions alone. Choose a tool and press a caption or
 * a word: each tool does to it what it does to a clip, and it saves itself.
 *
 * The words, the captions, the cues and the sound are served here rather than
 * made: the stack under test may run no audio engine, and what the lanes draw
 * is the question, not what joe hears.
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

const WORDS = [
  { start: 0.2, end: 0.5, text: 'Here', segment: 0 },
  { start: 1.0, end: 1.3, text: 'are', segment: 0 },
  { start: 1.6, end: 2.0, text: 'bars.', segment: 0 },
]
const CAPTIONS = [
  { start: 0.2, end: 1.4, text: 'Here are' },
  { start: 1.5, end: 2.2, text: 'bars.' },
]
const CUES = [
  { start: 0, end: 2.4, label: 'Opening', kind: 'chapter', state: null },
  { start: 1.5, end: 2.4, label: 'Excerpt 1', kind: 'excerpt', state: 'waiting' },
  { start: 0.7, end: null, label: 'A mark', kind: 'mark', state: null },
]
// Two values a second over a minute: quiet, then loud at the whole seconds.
const PEAKS = Array.from({ length: 120 }, (_, i) => (i % 2 ? 0.2 : 0.9))
const FADE_IN = 2

/**
 * Serve what the lanes draw of `project`: its words, captions and cues, the
 * sound of every file, and a two-second fade in on its first clip.
 */
async function serveLanes(page, project) {
  const id = project._id
  await page.route(
    url => url.pathname === `/project/${id}`,
    async route => {
      if (route.request().method() !== 'GET') return route.fallback()
      const response = await route.fetch()
      const json = await response.json()
      json.edl.clips[0].fadeIn = FADE_IN
      await route.fulfill({ response, json })
    }
  )
  await page.route(
    url => url.pathname === `/project/${id}/captions/words`,
    route => route.fulfill({ json: { words: WORDS } })
  )
  await page.route(
    url => url.pathname === `/project/${id}/captions`,
    route =>
      route.request().method() === 'GET'
        ? route.fulfill({ json: { captions: CAPTIONS, style: { enabled: false }, job: null } })
        : route.fallback()
  )
  await page.route(
    url => url.pathname === `/project/${id}/cues`,
    route => route.fulfill({ json: { cues: CUES } })
  )
  await page.route(
    url => /^\/media\/.+\/audio$/.test(url.pathname),
    route =>
      route.fulfill({
        json: {
          duration: 60,
          peaks: { rate: 2, values: PEAKS },
          silences: [{ start: 0, end: 0.5 }],
        },
      })
  )
}

/**
 * The lanes open on `project`, zoomed in two steps from the editor's default
 * so that each word has room for its text, with the words drawn.
 */
async function openLanes(page, project) {
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await expect(page.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
  const zoomIn = page.locator('.zoombar i', { hasText: 'zoom_in' })
  await zoomIn.click()
  await zoomIn.click()
  await expect(page.locator('.lane.text .laneword')).toHaveCount(WORDS.length)
  await expect(page.locator('.laneword', { hasText: 'are' })).toBeVisible()
}

const box = locator => locator.evaluate(n => n.getBoundingClientRect())

/** Pixels a second, as the first clip is drawn. */
async function scaleOf(page, project) {
  const clip = await box(page.locator('#timeline .clip').first())
  return clip.width / project.edl.clips[0].duration
}

/** Where `locator` starts, in seconds of the lanes' time axis. */
async function startOf(page, locator, scale) {
  const body = await box(page.locator('.lanebody'))
  const item = await box(locator)
  return (item.x - body.x) / scale
}

/**
 * The lanes open on the served project with `tool` chosen, the captions'
 * saves kept here and going no further -- the project's own captions are not
 * these tests' to write -- and a drag and a tap on what the lanes draw.
 */
async function withTool(page, request, token, tool) {
  const project = await mediaProject(request, token)
  await serveLanes(page, project)
  const saved = []
  await page.route(
    url => url.pathname === `/project/${project._id}/captions`,
    async route => {
      if (route.request().method() !== 'PUT') return route.fallback()
      const body = route.request().postDataJSON()
      saved.push(body)
      await route.fulfill({ json: { captions: body.captions, style: body.style, job: null } })
    }
  )
  await openLanes(page, project)
  const scale = await scaleOf(page, project)
  await page.locator(`#TTools [data-tool="${tool}"]`).click()
  const at = async (locator, along) => {
    const b = await box(locator)
    return { x: Math.round(b.x + b.width * along), y: Math.round(b.y + b.height / 2) }
  }
  return {
    saved,
    scale,
    /** Press `locator` `along` it and drag `seconds` along the timeline. */
    drag: async (locator, along, seconds) => {
      const { x, y } = await at(locator, along)
      await page.mouse.move(x, y)
      await page.mouse.down()
      await page.mouse.move(x + Math.round(seconds * scale), y, { steps: 6 })
      await page.mouse.up()
    },
    tap: async (locator, along) => {
      const { x, y } = await at(locator, along)
      await page.mouse.click(x, y)
    },
  }
}

/** The caption saved last that says `text`. */
const savedCaption = (saved, text) => saved[saved.length - 1].captions.find(c => c.text === text)

/** The word saved last that says `text`. */
const savedWord = (saved, text) => saved[saved.length - 1].words.find(w => w.text === text)

test.describe('the tools on the Text lane', () => {
  test('trim drags a caption by its nearer edge, and it saves itself', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, scale, drag } = await withTool(authedPage, request, token, 'trim')
    const caption = authedPage.locator('.lanecaption', { hasText: 'bars.' })

    // Pressed on its second half, its end follows: 2.2 s becomes about 3.
    await drag(caption, 0.8, 0.8)
    await expect.poll(() => saved.length).toBe(1)
    expect(savedCaption(saved, 'bars.').end).toBeCloseTo(3.0, 1)
    expect(savedCaption(saved, 'bars.').start).toBeCloseTo(1.5, 1)
    // Pressed on its first half, its start follows: 1.5 s becomes about 1.
    await drag(caption, 0.2, -0.5)
    await expect.poll(() => saved.length).toBe(2)
    expect(savedCaption(saved, 'bars.').start).toBeCloseTo(1.0, 1)
    expect(await startOf(authedPage, caption, scale)).toBeCloseTo(1.0, 1)
    // The words were not touched, so they were not sent.
    expect(saved[1].words).toBeUndefined()

    // A tap still takes the playhead to its start.
    await caption.click()
    await expect(authedPage.locator('p.timecode')).toHaveText(/^0:0(1\.0|0\.9)\d$/)
  })

  test('slide moves a caption with its neighbour, and move moves it alone', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, drag } = await withTool(authedPage, request, token, 'slide')
    // Slid 0.3 s earlier, the caption before it ends 0.3 s earlier too.
    await drag(authedPage.locator('.lanecaption', { hasText: 'bars.' }), 0.5, -0.3)
    await expect.poll(() => saved.length).toBe(1)
    expect(savedCaption(saved, 'bars.').start).toBeCloseTo(1.2, 1)
    expect(savedCaption(saved, 'bars.').end).toBeCloseTo(1.9, 1)
    expect(savedCaption(saved, 'Here are').end).toBeCloseTo(1.1, 1)

    // Moved half a second later, it keeps its length, and the other stays.
    await authedPage.locator('#TTools [data-tool="move"]').click()
    await drag(authedPage.locator('.lanecaption', { hasText: 'Here are' }), 0.5, 0.5)
    await expect.poll(() => saved.length).toBe(2)
    expect(savedCaption(saved, 'Here are').start).toBeCloseTo(0.7, 1)
    expect(savedCaption(saved, 'Here are').end).toBeCloseTo(1.6, 1)
    expect(savedCaption(saved, 'bars.').start).toBeCloseTo(1.2, 1)
  })

  test('dual roller moves where two captions meet, the edge nearer the press', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, drag } = await withTool(authedPage, request, token, 'dual roller')
    // Pressed on the first half of the second caption: its meeting with the first.
    await drag(authedPage.locator('.lanecaption', { hasText: 'bars.' }), 0.2, 0.3)
    await expect.poll(() => saved.length).toBe(1)
    expect(savedCaption(saved, 'Here are').end).toBeCloseTo(1.7, 1)
    expect(savedCaption(saved, 'bars.').start).toBeCloseTo(1.8, 1)
    expect(savedCaption(saved, 'bars.').end).toBeCloseTo(2.2, 1)
  })

  test('cut splits a caption where it is tapped, its text at its words', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, tap } = await withTool(authedPage, request, token, 'cut')
    // Tapped half way, at 0.8 s: one of its two words is said before.
    await tap(authedPage.locator('.lanecaption', { hasText: 'Here are' }), 0.5)
    await expect(authedPage.locator('.lanecaption')).toHaveCount(3)
    await expect.poll(() => saved.length).toBe(1)
    expect(savedCaption(saved, 'Here').end).toBeCloseTo(0.8, 1)
    expect(savedCaption(saved, 'are').start).toBeCloseTo(0.8, 1)
    expect(savedCaption(saved, 'are').end).toBeCloseTo(1.4, 1)
    // The playhead goes to the cut, as a clip's cut puts it.
    await expect(authedPage.locator('p.timecode')).toHaveText(/^0:00\.[78]\d$/)

    // A caption of one word says why it is not cut.
    await tap(authedPage.locator('.lanecaption', { hasText: 'bars.' }), 0.5)
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: 'A caption of one word cannot be split.' })
    ).toBeVisible()
  })

  test('slip keeps a caption in place and shows the words said under it', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, drag } = await withTool(authedPage, request, token, 'slip')
    // Dragged half a second along, the first caption shows what is said from
    // 0.7 to 1.9 s; dragged further, it stops where the transcript ends.
    await drag(authedPage.locator('.lanecaption', { hasText: 'Here are' }), 0.5, 0.5)
    await expect.poll(() => saved.length).toBe(1)
    const first = saved[0].captions[0]
    expect(first.text).toBe('are bars.')
    expect(first.start).toBeCloseTo(0.2, 2)
    expect(first.end).toBeCloseTo(1.4, 2)
  })

  test('a word is trimmed and moved between its neighbours, and saved with the captions', async ({
    authedPage,
    request,
    token,
  }) => {
    const { saved, drag, tap } = await withTool(authedPage, request, token, 'trim')
    // Its end dragged well past the next word's start stops there.
    await drag(authedPage.locator('.laneword', { hasText: 'are' }), 0.9, 1)
    await expect.poll(() => saved.length).toBe(1)
    expect(savedWord(saved, 'are').end).toBeCloseTo(1.6, 2)
    expect(saved[0].captions).toHaveLength(2)

    // Moved well past the word after it, it stops against it.
    await authedPage.locator('#TTools [data-tool="move"]').click()
    await drag(authedPage.locator('.laneword', { hasText: 'Here' }), 0.5, 1)
    await expect.poll(() => saved.length).toBe(2)
    expect(savedWord(saved, 'Here').start).toBeCloseTo(0.7, 2)
    expect(savedWord(saved, 'Here').end).toBeCloseTo(1.0, 2)

    // A word is not cut, and says so.
    await authedPage.locator('#TTools [data-tool="cut"]').click()
    await tap(authedPage.locator('.laneword', { hasText: 'bars.' }), 0.5)
    await expect(
      authedPage.locator('.ajs-message').filter({ hasText: 'A word cannot be split.' })
    ).toBeVisible()
    expect(saved).toHaveLength(2)
  })
})

test.describe('the lanes', () => {
  test('every lane is drawn, the clips among them', async ({ authedPage, request, token }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)

    await expect(authedPage.locator('.lanes .lanelabel')).toHaveText([
      'Time',
      'Clips',
      'Text',
      'Audio',
      'FX',
      'Cues',
    ])
    // The clip strip is the Clips lane: the same element the tools act on.
    await expect(authedPage.locator('.lane.clips #timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await expect(authedPage.locator('.lane.ruler .tick').first()).toHaveText('0:00')
    await expect(authedPage.locator('.playhead')).toBeVisible()
  })

  test('the lanes agree on where a second is', async ({ authedPage, request, token }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)
    const scale = await scaleOf(authedPage, project)
    expect(scale).toBeGreaterThan(1)
    const at = locator => startOf(authedPage, locator, scale)

    // The first clip starts where the axis does.
    expect(await at(authedPage.locator('#timeline .clip').first())).toBeCloseTo(0, 1)
    // Mutation: lay the words out from the lane's padding edge -- fails.
    expect(await at(authedPage.locator('.laneword', { hasText: 'are' }))).toBeCloseTo(1.0, 1)
    expect(await at(authedPage.locator('.lanecaption', { hasText: 'bars.' }))).toBeCloseTo(1.5, 1)
    expect(await at(authedPage.locator('.cue.excerpt'))).toBeCloseTo(1.5, 1)
    expect(await at(authedPage.locator('.cue.point'))).toBeCloseTo(0.7, 1)
    expect(await at(authedPage.locator('.lane.ruler .tick', { hasText: /^0:02$/ }))).toBeCloseTo(
      2,
      1
    )

    // A fade in is as wide as it is long, from the clip's start.
    const fade = authedPage.locator('.lane.fx .fade.in')
    expect(await at(fade)).toBeCloseTo(0, 1)
    expect((await box(fade)).width / scale).toBeCloseTo(FADE_IN, 1)
    await expect(fade).toHaveAttribute('title', `Fade in, ${FADE_IN} s`)

    // The sound is drawn over the whole timeline, at the same scale.
    const svg = authedPage.locator('.lane.audio svg')
    await expect(svg.locator('polygon.envelope')).toHaveCount(1)
    const duration = project.edl.clips.reduce((sum, c) => sum + c.duration, 0)
    expect((await box(svg)).width / scale).toBeCloseTo(duration, 1)
  })

  test('a press on a lane seeks there, and the playhead follows', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)
    const scale = await scaleOf(authedPage, project)
    // Zooming in pressed a button at the foot of the panel, which may have
    // scrolled the ruler out of it; a press lands where the ruler is seen.
    await authedPage.locator('.lane.ruler').scrollIntoViewIfNeeded()
    const body = await box(authedPage.locator('.lanebody'))
    const ruler = await box(authedPage.locator('.lane.ruler'))

    // Whole pixels: a press at a fraction of one lands a hundredth early.
    await authedPage.mouse.click(Math.round(body.x + 1.6 * scale), ruler.y + ruler.height / 2)
    await expect(authedPage.locator('p.timecode')).toHaveText(/^0:01\.[56]\d$/)
    expect(await startOf(authedPage, authedPage.locator('.playhead'), scale)).toBeCloseTo(1.6, 1)

    // The word and the caption under the playhead are marked.
    await expect(authedPage.locator('.lanecaption.on')).toHaveText('bars.')
    await authedPage.mouse.click(Math.round(body.x + 1.1 * scale), ruler.y + ruler.height / 2)
    await expect(authedPage.locator('.laneword.current')).toHaveText('are')
    await expect(authedPage.locator('.lanecaption.on')).toHaveText('Here are')
  })

  test('a word, a caption and a cue each take the playhead to their start', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)
    const timecode = authedPage.locator('p.timecode')

    await authedPage.locator('.cue.excerpt').click()
    await expect(timecode).toHaveText('0:01.50')
    await authedPage.locator('.laneword', { hasText: 'Here' }).click()
    await expect(timecode).toHaveText('0:00.20')
    await authedPage.locator('.lanecaption', { hasText: 'bars.' }).click()
    await expect(timecode).toHaveText('0:01.50')
    await authedPage.locator('.cue.point').click()
    await expect(timecode).toHaveText('0:00.70')
  })

  test('a cue says what it is, and where it stands', async ({ authedPage, request, token }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)

    const excerpt = authedPage.locator('.cue.excerpt')
    await expect(excerpt).toHaveText('Excerpt 1')
    await expect(excerpt).toHaveClass(/waiting/)
    await expect(excerpt).toHaveAttribute('title', /Excerpt 1 · 0:01\.5–0:02\.4 · waiting/)
    // Chapters sit on the row above the rest.
    const chapter = await box(authedPage.locator('.cue.chapter'))
    expect((await box(excerpt)).y).toBeGreaterThan(chapter.y)
  })

  test('zoomed out, the words become marks and then make way', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await serveLanes(authedPage, project)
    await openLanes(authedPage, project)
    await expect(authedPage.locator('.laneword', { hasText: 'are' })).toBeVisible()

    // One step out draws a word narrower than its text: a mark.
    const out = authedPage.locator('.zoombar i', { hasText: 'zoom_out' })
    await out.click()
    await expect(authedPage.locator('.laneword.mark')).toHaveCount(WORDS.length)
    await expect(authedPage.locator('.laneword').first()).toHaveText('')
    // Five more, and only the captions are left to read.
    for (let step = 0; step < 5; step++) await out.click()
    await expect(authedPage.locator('.laneword')).toHaveCount(0)
    await expect(authedPage.locator('.lanecaption')).toHaveCount(CAPTIONS.length)
  })
})
