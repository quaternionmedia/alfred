/**
 * Each timeline tool chosen and its edit made, saved as
 * `docs/assets/screens/tools/<tool>.png` for docs/tools.md. @screens, docs project.
 */

const { test, expect } = require('./fixtures')
const {
  DESKTOP,
  arrange,
  auth,
  clear,
  demoMedia,
  makeProject,
  onClip,
  openProject,
  playhead,
  save,
  screenFile,
} = require('./screens-kit')

const PROJECT = 'tools demo'

// Panels closed so the viewer and timeline take the full width.
const ASIDE = ['projects', 'media', 'template', 'transcript', 'render', 'deliver', 'captions']

// Zoom-in presses: about 200 px a second, room for each clip's label.
const ZOOMS = 3

let project

/** bars 0.5-2 s of its file, a 1 s title, testcard 0.5-2 s. */
const clips = media => [
  { type: 'video', name: media['demo-bars.mp4'], start: 0, inpoint: 0.5, outpoint: 2, duration: 1.5 },
  { type: 'template', name: 'title', start: 1.5, duration: 1, data: { text: 'alfred', color: '#f2aa4c' } },
  { type: 'video', name: media['demo-testcard.mp4'], start: 2.5, inpoint: 0.5, outpoint: 2, duration: 1.5 },
]

/** The project open, the side panels closed, zoomed in `zooms` times. */
async function open(page, zooms = ZOOMS) {
  await openProject(page, project)
  await arrange(page, { closing: ASIDE, zooms })
}

async function choose(page, tool) {
  const button = page.locator(`#TTools [data-tool="${tool}"]`)
  await button.click()
  await expect(button).toHaveAttribute('aria-pressed', 'true')
}

/** Mouse drag by `dx` px. Starts on a whole pixel so the times land round. */
async function drag(page, from, dx) {
  const x = Math.round(from.x)
  const y = Math.round(from.y)
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + dx, y, { steps: 10 })
  await page.mouse.up()
}

async function pixelsPerSecond(page) {
  const box = await page.locator('#timeline .clip').first().boundingBox()
  return box.width / project.edl.clips[0].duration
}

/** Each clip's label: name, then in-point and out-point for media. */
const labels = page =>
  page.locator('#timeline .clip').evaluateAll(clips =>
    clips.map(clip =>
      ['.clipname', '.inpoint', '.outpoint']
        .map(part => clip.querySelector(part))
        .filter(Boolean)
        .map(part => part.textContent.trim())
        .join(' ')
    )
  )

test.use({ video: 'off' })

test.describe('@screens', () => {
  test.use({ viewport: DESKTOP })

  test.beforeAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      project = await makeProject(api, token, PROJECT, clips(await demoMedia(api, token)))
    } finally {
      await api.dispose()
    }
  })

  test.afterAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      if (project) await api.delete(`/project/${project._id}`, auth(token))
    } finally {
      await api.dispose()
    }
  })

  test('screen: time moves the playhead to where you press', async ({ page }) => {
    const file = screenFile('tools', 'time')
    clear(file)
    await open(page)
    await choose(page, 'time')

    const at = await onClip(page, 2, 0.5)
    await page.mouse.click(at.x, at.y)
    await expect.poll(() => playhead(page)).toBeCloseTo(3.25, 1)
    await save(page, file)
  })

  test('screen: trim drags the end of a clip', async ({ page }) => {
    const file = screenFile('tools', 'trim')
    clear(file)
    await open(page)
    await choose(page, 'trim')
    const second = await pixelsPerSecond(page)

    await drag(page, await onClip(page, 0, 0.95), -second / 4)
    await expect.poll(() => labels(page)).toEqual([
      'demo-bars.mp4 0.5 1.75',
      'alfred',
      'demo-testcard.mp4 0.5 2',
    ])
    const bars = await page.locator('#timeline .clip').first().boundingBox()
    expect(bars.width).toBeCloseTo(1.25 * second, -1)
    await save(page, file)
  })

  test('screen: move drags a clip to another place in the order', async ({ page }) => {
    const file = screenFile('tools', 'move')
    clear(file)
    await open(page)
    await choose(page, 'move')

    // Positions read before the drag: Sortable adds a clone while dragging.
    const from = await onClip(page, 2, 0.5)
    const stops = [await onClip(page, 1, 0.3), await onClip(page, 0, 0.05)]
    await page.mouse.move(from.x, from.y)
    await page.mouse.down()
    // Pause at each stop: Sortable ignores moves while it animates (150 ms).
    for (const stop of stops) {
      await page.mouse.move(stop.x, stop.y, { steps: 10 })
      await page.waitForTimeout(300)
    }
    await page.mouse.up()
    await expect.poll(() => labels(page)).toEqual([
      'demo-testcard.mp4 0.5 2',
      'demo-bars.mp4 0.5 2',
      'alfred',
    ])
    await save(page, file)
  })

  test('screen: cut splits a clip where you press', async ({ page }) => {
    const file = screenFile('tools', 'cut')
    clear(file)
    await open(page)
    await choose(page, 'cut')

    const at = await onClip(page, 1, 0.5)
    await page.mouse.click(at.x, at.y)
    await expect.poll(() => labels(page)).toEqual([
      'demo-bars.mp4 0.5 2',
      'alfred',
      'alfred',
      'demo-testcard.mp4 0.5 2',
    ])
    await expect.poll(() => playhead(page)).toBeCloseTo(2, 1)
    await save(page, file)
  })

  test('screen: slip changes which part of its file a clip plays', async ({ page }) => {
    const file = screenFile('tools', 'slip')
    clear(file)
    await open(page)
    // Playhead on the test card first, so the viewer's counter shows the slip.
    const on = await onClip(page, 2, 0.5)
    await page.mouse.click(on.x, on.y)
    await expect.poll(() => playhead(page)).toBeCloseTo(3.25, 1)

    await choose(page, 'slip')
    const second = await pixelsPerSecond(page)
    await drag(page, await onClip(page, 2, 0.5), -second / 2)
    await expect.poll(() => labels(page)).toEqual([
      'demo-bars.mp4 0.5 2',
      'alfred',
      'demo-testcard.mp4 1 2.5',
    ])
    await save(page, file)
  })

  test('screen: slide moves a clip between its neighbours', async ({ page }) => {
    const file = screenFile('tools', 'slide')
    clear(file)
    await open(page)
    await choose(page, 'slide')
    const second = await pixelsPerSecond(page)

    await drag(page, await onClip(page, 1, 0.5), second / 4)
    await expect.poll(() => labels(page)).toEqual([
      'demo-bars.mp4 0.5 2.25',
      'alfred',
      'demo-testcard.mp4 0.75 2',
    ])
    await save(page, file)
  })

  test('screen: dual roller moves the cut between two clips', async ({ page }) => {
    const file = screenFile('tools', 'dual-roller')
    clear(file)
    await open(page)
    await choose(page, 'dual roller')
    const second = await pixelsPerSecond(page)

    // Pressed on the test card's first half: the cut at its start.
    await drag(page, await onClip(page, 2, 0.2), -second / 2)
    await expect.poll(() => labels(page)).toEqual([
      'demo-bars.mp4 0.5 2',
      'alfred',
      'demo-testcard.mp4 0 2',
    ])
    const title = await page.locator('#timeline .clip').nth(1).boundingBox()
    expect(title.width).toBeCloseTo(0.5 * second, -1)
    await save(page, file)
  })

  test('screen: zoom draws the timeline larger', async ({ page }) => {
    const file = screenFile('tools', 'zoom')
    clear(file)
    await open(page, 0)
    const before = await pixelsPerSecond(page)

    // One press past the other screens: the timeline outgrows its panel.
    const zoomIn = page.locator('.zoombar i', { hasText: 'zoom_in' })
    for (let i = 0; i <= ZOOMS; i++) await zoomIn.click()
    await expect.poll(() => pixelsPerSecond(page)).toBeGreaterThan(before * 5)
    await save(page, file)
  })
})
