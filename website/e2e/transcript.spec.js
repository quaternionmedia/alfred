/**
 * Editing by text: words deleted from the Transcript panel cut the timeline.
 *
 * # Recipe: cut the video by deleting words
 *
 * Select words, press Delete, Save. Desktop and phone; the @slow test transcribes via the stub engine.
 */

const { test, expect } = require('./fixtures')

// Stub engine fixture: tone at 0.5-1.5 and 2.0-3.2 s.
const FIXTURE = 'videos/e2e-speech.wav'

const auth = token => ({ headers: { Authorization: token } })

/** The speech, then 2 s of colour, placed end to end. */
const SPOKEN = {
  clips: [
    { type: 'audio', name: FIXTURE, duration: 4, start: 0, inpoint: 0, outpoint: 4, fadeIn: 0, fadeOut: 0 },
    { type: 'template', name: 'makeColor', duration: 2, start: 4, fadeIn: 0, fadeOut: 0, data: { color: '#203040' } },
  ],
  duration: 6,
}

/** Six seconds of colour, for words put on through the API. */
const COLOUR = {
  clips: [
    { type: 'template', name: 'makeColor', duration: 3, start: 0, fadeIn: 0, fadeOut: 0, data: { color: '#203040' } },
    { type: 'template', name: 'makeColor', duration: 3, start: 3, fadeIn: 0, fadeOut: 0, data: { color: '#402030' } },
  ],
  duration: 6,
}

/** One word a second from `start`, in `segment`. */
const spoken = (start, text, segment) =>
  text.split(' ').map((word, i) => ({ start: start + i, end: start + i + 1, text: word, segment }))

const WORDS = [...spoken(0, 'One two three', 0), ...spoken(3, 'four five six', 1)]
const CAPTIONS = [
  { start: 0, end: 3, text: 'One two three' },
  { start: 3, end: 6, text: 'four five six' },
]

/** A project of the caller's own for one test, removed after it. */
async function withProject(request, token, edl, use) {
  const created = await request.post('/project', {
    ...auth(token),
    data: {
      name: `transcript ${test.info().title.slice(0, 40)} ${test.info().workerIndex}-${Date.now()}`,
      logic: {},
      edl,
    },
  })
  expect(created.status(), await created.text()).toBe(200)
  const project = await created.json()
  try {
    await use(project)
  } finally {
    await request.delete(`/project/${project._id}`, auth(token))
  }
}

async function wordsOf(request, token, project) {
  const res = await request.get(`/project/${project._id}/captions/words`, auth(token))
  expect(res.status()).toBe(200)
  return (await res.json()).words
}

async function captionsOf(request, token, project) {
  return (await (await request.get(`/project/${project._id}/captions`, auth(token))).json()).captions
}

async function timelineOf(request, token, project) {
  return (await (await request.get(`/project/${project._id}`, auth(token))).json()).edl
}

/** Store `words` and `captions` as a transcription would. */
async function transcribed(request, token, project, words = WORDS, captions = CAPTIONS) {
  const res = await request.put(`/project/${project._id}/captions`, {
    ...auth(token),
    data: { captions, words },
  })
  expect(res.status(), await res.text()).toBe(200)
}

/** Seconds to the ms; null stays null. */
const ms = n => (n === null || n === undefined ? null : Math.round(Number(n) * 1000) / 1000)

/** The playhead, from the transport's timecode. */
const playhead = async page => {
  const [m, s] = (await page.locator('.timecode').innerText()).split(':')
  return Number(m) * 60 + Number(s)
}

const words = page => page.locator('#transcript-text .word')
const going = page => page.locator('#transcript-text .word.going')

/** Open Edit with the Transcript panel shown: its tab at 1200x800, the stage's switch on a phone. */
async function openTranscript(page, project) {
  if (test.info().project.name !== 'phone') await page.setViewportSize({ width: 1200, height: 800 })
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await expect(page.locator('#timeline .clip').first()).toBeVisible()
  const tab = page.locator('#paneltab-transcript')
  if (test.info().project.name === 'phone') {
    // No tab: the Edit stage's switch, Captions shown until it is used.
    await expect(tab).toHaveCount(0)
    await expect(page.locator('#panel-captions')).toBeVisible()
    await page.locator('#flowswitch-transcript').click()
    await expect(page.locator('#panel-captions')).toHaveCount(0)
  } else {
    await tab.click()
  }
  await expect(page.locator('#panel-transcript')).toBeVisible()
}

/** Mouse-drag from word `a` to word `b`. */
async function dragAcross(page, a, b) {
  await a.scrollIntoViewIfNeeded()
  const from = await a.boundingBox()
  const to = await b.boundingBox()
  await page.mouse.move(from.x + 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width - 2, to.y + to.height / 2, { steps: 8 })
  await page.mouse.up()
}

/** Skip without an audio engine, as captions.spec.js does. */
async function needEngine(request, token) {
  const health = await (await request.get('/health', auth(token))).json()
  const engine = health.audio_engine || {}
  test.skip(!engine.configured, 'no audio engine is configured on this stack')
  test.skip(/vox\.media/.test(engine.detail || ''), `the vendored vox has no media client: ${engine.detail}`)
  expect(engine.ok, engine.detail).toBe(true)
}

test.describe('@slow from the transcription to the cut', () => {
  test('words deleted from the transcript cut the timeline, the captions and the words', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Transcribe from the empty panel, delete "first thing": timeline, captions
     * and words all lose the half second, saved together.
     */
    test.setTimeout(180_000)
    await needEngine(request, token)
    await withProject(request, token, SPOKEN, async project => {
      await openTranscript(authedPage, project)
      await expect(authedPage.locator('#transcript-empty')).toContainText('No transcript yet')
      await authedPage.locator('#transcript-transcribe').click()
      await expect(authedPage.locator('#transcript-job')).toHaveAttribute('data-state', 'done', {
        timeout: 150_000,
      })

      await expect(words(authedPage)).toHaveCount(9)
      await expect(authedPage.locator('#transcript-text .transcriptpara')).toHaveText([
        'the first thing said',
        'and then a second line',
      ])
      const heard = await wordsOf(request, token, project)
      const [first, thing] = [heard[1], heard[2]]
      expect([first.text, thing.text]).toEqual(['first', 'thing'])
      const before = await captionsOf(request, token, project)
      expect(before.map(c => c.text)).toEqual(['the first thing said', 'and then a second line'])

      // Click, shift-click: both struck through.
      await words(authedPage).nth(1).click()
      await words(authedPage).nth(2).click({ modifiers: ['Shift'] })
      await expect(going(authedPage)).toHaveText(['first', 'thing'])
      await expect(authedPage.locator('#transcript-cut')).toContainText('Cut 2 words')

      await authedPage.keyboard.press('Delete')
      await expect(words(authedPage)).toHaveCount(7)
      await expect(authedPage.locator('#transcript-text .transcriptpara').first()).toHaveText('the said')
      await expect(going(authedPage)).toHaveCount(0)
      await expect(authedPage.locator('#transcript-unsaved')).toBeVisible()
      // The sound clip is split: three clips.
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(3)

      const removed = Math.round((thing.end - first.start) * 1000) / 1000
      await authedPage.locator('#transcript-save').click()
      await expect(authedPage.locator('#transcript-unsaved')).toHaveCount(0)

      // Mutation: don't shift parts after the cut -- fails.
      const edl = await timelineOf(request, token, project)
      expect(ms(edl.duration)).toBe(ms(6 - removed))
      expect(edl.clips.map(c => [c.name, ms(c.start), ms(c.inpoint), ms(c.outpoint)])).toEqual([
        [FIXTURE, 0, 0, ms(first.start)],
        [FIXTURE, ms(first.start), ms(thing.end), 4],
        ['makeColor', ms(4 - removed), null, null],
      ])

      const after = await captionsOf(request, token, project)
      // First caption trimmed, second moved up.
      expect(after[0].start).toBeCloseTo(before[0].start, 3)
      expect(after[0].end).toBeCloseTo(before[0].end - removed, 3)
      expect(after[1].start).toBeCloseTo(before[1].start - removed, 3)
      expect(after[1].end).toBeCloseTo(before[1].end - removed, 3)

      const kept = await wordsOf(request, token, project)
      expect(kept.map(w => w.text)).toEqual(['the', 'said', 'and', 'then', 'a', 'second', 'line'])
      expect(kept[1].start).toBeCloseTo(first.start, 3)
      expect(kept[2].start).toBeCloseTo(heard[4].start - removed, 3)
    })
  })
})

test.describe('the transcript', () => {
  test('a drag selects words, and Cut takes them, however they were selected', async ({
    authedPage,
    request,
    token,
  }) => {
    /** "three four" spans the clip boundary: both clips lose a second. */
    await withProject(request, token, COLOUR, async project => {
      await transcribed(request, token, project)
      await openTranscript(authedPage, project)
      await expect(words(authedPage)).toHaveCount(6)

      await dragAcross(authedPage, words(authedPage).nth(2), words(authedPage).nth(3))
      await expect(going(authedPage)).toHaveText(['three', 'four'])
      await expect(authedPage.locator('#transcript-cut')).toContainText('Cut 2 words, 2 s')
      await authedPage.locator('#transcript-cut').click()

      await expect(words(authedPage)).toHaveText(['One', 'two', 'five', 'six'])
      await expect(authedPage.locator('#transcript-last')).toContainText('2 s shorter')
      // End: playhead to the timeline's end.
      await authedPage.keyboard.press('End')
      await expect.poll(() => playhead(authedPage)).toBeCloseTo(4, 1)

      await authedPage.locator('#transcript-save').click()
      await expect(authedPage.locator('#transcript-unsaved')).toHaveCount(0)
      const edl = await timelineOf(request, token, project)
      expect(edl.clips.map(c => [c.start, c.duration, c.inpoint ?? null])).toEqual([
        [0, 2, null],
        // Resumes one second in.
        [2, 2, 1],
      ])
      expect(await captionsOf(request, token, project)).toEqual([
        { start: 0, end: 2, text: 'One two three' },
        { start: 2, end: 4, text: 'four five six' },
      ])
    })
  })

  test('a double-click selects one word, and Backspace cuts it', async ({
    authedPage,
    request,
    token,
  }) => {
    /** The cut stays the page's until Save. */
    await withProject(request, token, COLOUR, async project => {
      await transcribed(request, token, project)
      await openTranscript(authedPage, project)
      await words(authedPage).nth(4).dblclick()
      await expect(going(authedPage)).toHaveText(['five'])
      await authedPage.keyboard.press('Backspace')
      await expect(words(authedPage)).toHaveText(['One', 'two', 'three', 'four', 'six'])
      // Unsaved until Save.
      expect((await wordsOf(request, token, project)).length).toBe(6)
    })
  })

  test('clicking a word moves the playhead to it, and the word playing is marked', async ({
    authedPage,
    request,
    token,
  }) => {
    /** Click seeks and drops the selection; Escape drops it; playback marks the word. */
    await withProject(request, token, COLOUR, async project => {
      await transcribed(request, token, project)
      await openTranscript(authedPage, project)

      await words(authedPage).nth(3).click()
      await expect.poll(() => playhead(authedPage)).toBeCloseTo(3, 1)
      await expect(words(authedPage).nth(3)).toHaveClass(/current/)
      await expect(going(authedPage)).toHaveCount(0)

      await dragAcross(authedPage, words(authedPage).nth(0), words(authedPage).nth(1))
      await expect(going(authedPage)).toHaveCount(2)
      await authedPage.keyboard.press('Escape')
      await expect(going(authedPage)).toHaveCount(0)
      await expect(authedPage.locator('#transcript-cut')).toBeDisabled()

      // Playing from "four" moves the mark to "five".
      await authedPage.locator('#playpause').click()
      await expect(words(authedPage).nth(4)).toHaveClass(/current/, { timeout: 5000 })
      await authedPage.locator('#playpause').click()
    })
  })

  test('without a transcript the panel says how to get one', async ({ authedPage, request, token }) => {
    /** One line and a Transcribe button. */
    await withProject(request, token, COLOUR, async project => {
      await openTranscript(authedPage, project)
      await expect(authedPage.locator('#transcript-empty')).toBeVisible()
      await expect(authedPage.locator('#transcript-transcribe')).toBeVisible()
      await expect(words(authedPage)).toHaveCount(0)
      await expect(authedPage.locator('#transcript-cut')).toHaveCount(0)
    })
  })
})
