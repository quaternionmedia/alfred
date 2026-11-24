/**
 * One video made in the editor, from an empty project to a delivered render:
 * the steps docs/guide.md walks. Used by its recipe (recipes.spec.js) and its
 * screenshots (screens-guide.spec.js).
 */

const { expect, expectSaved, savesSoFar } = require('./fixtures')

// What `POST /demo/media` makes, 3 s each, and the two the walk puts on.
const DEMO_MEDIA = ['demo-bars.mp4', 'demo-colour.mp4', 'demo-testcard.mp4']
const PICTURES = ['videos/demo-bars.mp4', 'videos/demo-testcard.mp4']

// The sound transcribed: the stub's two tones, where the stub is the engine (test_e2e.yml).
const STUB_SPEECH = process.env.E2E_AUDIO_ENGINE_URL ? 'videos/e2e-speech.wav' : ''
// Or a file of speech for joe: someone's own, so for recordings only, never screenshots.
const SPEECH = process.env.E2E_SPEECH || STUB_SPEECH

/** The library files a walk with `speech` may show. */
const library = speech => [...DEMO_MEDIA, speech.split('/').pop()]

const PROJECT = 'My first video'
const TITLE = 'My first video'

// Each step's picture, in order: docs/assets/screens/guide/<step>.png.
const STEPS = [
  'open',
  'media',
  'title',
  'transcribe',
  'edit-by-text',
  'captions',
  'render',
  'deliver',
]

// A render of 13 s at 640x360, and a transcription by a speech model on a CPU.
const RENDER_TIMEOUT = 150_000
const TRANSCRIBE_TIMEOUT = 150_000

const auth = token => ({ headers: { Authorization: token } })

/** Why the walk cannot run here with `speech`, or '' when it can. */
async function cannotWalk(request, token, speech) {
  if (!speech) return 'no sound to transcribe: no stub engine, and no E2E_SPEECH'
  const health = await (await request.get('/health', auth(token))).json()
  const engine = health.audio_engine || {}
  if (!engine.configured) return 'no audio engine is configured on this stack'
  if (!engine.ok) return `the audio engine does not answer: ${engine.detail}`
  if (!(health.renderer || {}).workers) return 'no render worker is running'
  expect((await request.post('/demo/media', auth(token))).status()).toBe(200)
  const videos = (await (await request.get('/videos', auth(token))).json()).map(String)
  if (!videos.includes(speech)) return `no ${speech} in the library`
  return ''
}

/** The project the walk fills: nothing on its timeline yet. */
async function emptyProject(request, token) {
  const created = await request.post('/project', {
    ...auth(token),
    data: { name: PROJECT, logic: {}, fields: [], edl: { clips: [], duration: 0 } },
  })
  expect(created.status(), await created.text()).toBe(200)
  return created.json()
}

/** Delete `project`, and its renders once the worker is done with them. */
async function removeProject(request, token, project) {
  const renders = (await (await request.get('/render', auth(token))).json()).filter(
    render => render.project_id === project._id
  )
  for (const render of renders) {
    await expect
      .poll(
        async () =>
          (await (await request.get(`/render/${render._id}/status`, auth(token))).json()).state,
        { timeout: RENDER_TIMEOUT, intervals: [1000] }
      )
      .toMatch(/rendered|failed/)
    await request.delete(`/render/${render._id}`, auth(token))
  }
  await request.delete(`/project/${project._id}`, auth(token))
}

const clips = page => page.locator('#timeline .clip')
const words = page => page.locator('#transcript-text .word')

/** `text` without the first of each of `cut`, as whole words. */
function without(text, cut) {
  for (const word of cut) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    text = text.replace(new RegExp(`(^|\\s)${escaped}(?=\\s|$)`), '$1')
  }
  return text.replace(/\s+/g, ' ').trim()
}

/** Zoom out until the whole timeline fits its panel. */
async function fitTimeline(page) {
  const timeline = page.locator('#timeline')
  const zoomOut = page.locator('.zoombar i', { hasText: 'zoom_out' })
  for (let press = 0; press < 8; press++) {
    if (await timeline.evaluate(box => box.scrollWidth <= box.clientWidth)) return
    await zoomOut.click()
    await page.evaluate(() => new Promise(done => requestAnimationFrame(done)))
  }
}

/** Drag clip `from` to the front with the move tool, through each clip before it. */
async function moveToFront(page, from) {
  const at = async (index, along) => {
    const box = await clips(page).nth(index).boundingBox()
    return { x: box.x + box.width * along, y: box.y + box.height / 2 }
  }
  // Read before the drag: Sortable adds a clone while dragging.
  const start = await at(from, 0.5)
  const stops = []
  for (let index = from - 1; index >= 0; index--) stops.push(await at(index, index ? 0.3 : 0.05))
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  // Sortable ignores moves while it animates (150 ms).
  for (const stop of stops) {
    await page.mouse.move(stop.x, stop.y, { steps: 10 })
    await page.waitForTimeout(300)
  }
  await page.mouse.up()
}

async function choose(page, tool) {
  const button = page.locator(`#TTools [data-tool="${tool}"]`)
  await button.click()
  await expect(button).toHaveAttribute('aria-pressed', 'true')
}

/**
 * Walk `project` from nothing to a delivered render. `shown(step)` runs as
 * each step's result is on the screen; `pause(ms)` between the actions in it.
 */
async function walk(page, { project, speech, request, token }, { shown, pause = async () => {} }) {
  // Open the editor: nothing chosen yet.
  await page.goto('/')
  await expect(page.locator('#preview.empty')).toContainText('Nothing on the timeline yet')
  await shown('open')

  // Bring media: the project, then two pictures and the sound, each on the end.
  await page.locator('#stage-source').click()
  await page.locator('.projectchoice', { hasText: project.name }).click()
  await expect(page).toHaveURL(new RegExp(`project=${project._id}`))
  await pause()
  for (const [count, name] of [...PICTURES, speech].entries()) {
    await page.locator(`.mediachoice[data-media="${name}"]`).click()
    await expect(clips(page)).toHaveCount(count + 1)
    await pause(600)
  }
  await expect(page.locator('#media-added')).toContainText('clip 3 on the timeline')
  await fitTimeline(page)
  // Playhead back on the bars: the sound has no picture.
  await clips(page).first().click()
  await shown('media')

  // A title: on the end, its text and length typed, then moved to the front.
  await page.locator('.templatechoice[data-template="title"]').click()
  await expect(clips(page)).toHaveCount(4)
  await page.locator('#param-text').fill(TITLE)
  await page.locator('#param-duration').fill('3')
  await expect(clips(page).nth(3)).toContainText(TITLE)
  await pause()
  await fitTimeline(page)
  await choose(page, 'move')
  await moveToFront(page, 3)
  await expect(clips(page).first()).toContainText(TITLE)
  await choose(page, 'time')
  await clips(page).first().click()
  await expect(page.locator('#param-text')).toHaveValue(TITLE)
  // The timeline saves itself: the server has all four.
  await expect
    .poll(
      async () =>
        (await (await request.get(`/project/${project._id}`, auth(token))).json()).edl.clips
          .length
    )
    .toBe(4)
  await shown('title')

  // Transcribe the sound, in the Transcript panel.
  await page.locator('#paneltab-transcript').click()
  await expect(page.locator('#transcript-empty')).toBeVisible()
  const transcribe = page.locator('#transcript-transcribe')
  await expect(transcribe).toBeEnabled({ timeout: 30_000 })
  await pause()
  await transcribe.click()
  await expect(page.locator('#transcript-job')).toHaveAttribute('data-state', 'done', {
    timeout: TRANSCRIBE_TIMEOUT,
  })
  await expect.poll(() => words(page).count()).toBeGreaterThan(2)
  await shown('transcribe')

  // Edit by text: the second and third words selected, then cut.
  await words(page).nth(1).click()
  await words(page).nth(2).click({ modifiers: ['Shift'] })
  const going = page.locator('#transcript-text .word.going')
  await expect(going).toHaveCount(2)
  const cut = await going.allTextContents()
  await shown('edit-by-text')
  const before = await words(page).count()
  const saves = await savesSoFar(page)
  await page.keyboard.press('Delete')
  await expect(page.locator('#transcript-last')).toContainText('Cut 2 words')
  await expect.poll(() => words(page).count()).toBeLessThan(before)
  await expect.poll(() => clips(page).count()).toBeGreaterThan(4)
  // The cut saves itself, with the captions and the words it moved.
  await expectSaved(page, { since: saves, id: 'transcript-save-state' })
  await pause()

  // Captions: the first one's text without the words cut, then a style, saved.
  await page.locator('#paneltab-captions').click()
  const first = page.getByLabel('Caption 1 text')
  await first.fill(without(await first.inputValue(), cut))
  await pause()
  await page.locator('#caption-enabled').check()
  await page.locator('#caption-size').fill('64')
  await page.locator('#caption-color').fill('#f2aa4c')
  await pause()
  await page.locator('#captions-save').click()
  await expect(page.locator('#captions-unsaved')).toHaveCount(0)
  // Playhead on the first word: its caption over the picture, as renders draw it.
  await words(page).first().click()
  const overlay = page.locator('#caption-overlay')
  await expect(overlay).toHaveAttribute('data-drawn', 'true')
  await expect(overlay).not.toBeEmpty()
  await shown('captions')

  // Render: a small one, from the title.
  await page.locator('#stage-render').click()
  await clips(page).first().click()
  await page.locator('#render-width').fill('640')
  await page.locator('#render-height').fill('360')
  await expect(page.locator('#queue-render')).toBeEnabled()
  await shown('render')
  await page.locator('#queue-render').click()

  // Deliver: once it is rendered, to the destination chosen above the list.
  const row = page.locator('#panel-deliver .renderitem')
  await expect(row).toHaveCount(1, { timeout: 30_000 })
  await expect(row).toHaveAttribute('data-state', 'rendered', { timeout: RENDER_TIMEOUT })
  await pause()
  await row.locator('button.deliver').click()
  await expect(row.locator('.delivered')).toHaveText(/delivered → local/)
  await shown('deliver')
}

module.exports = {
  PROJECT,
  SPEECH,
  STEPS,
  STUB_SPEECH,
  cannotWalk,
  emptyProject,
  library,
  removeProject,
  walk,
}
