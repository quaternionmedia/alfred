/**
 * Each docs example opened in the editor at its moment, saved as
 * `docs/assets/screens/examples/<name>.png`. @screens, docs project.
 */

const { test, expect } = require('./fixtures')
const { editorClips, examples, moment } = require('./docs-examples')
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

// Left panels closed: room for each clip's label.
const ASIDE = ['projects', 'media']

// Zoom-in presses at most, each kept only if the timeline still fits.
const ZOOMS = 2

/** Zoom in while the whole timeline fits its panel. */
async function zoomToFit(page) {
  const timeline = page.locator('#timeline')
  const drawn = () => page.evaluate(() => new Promise(done => requestAnimationFrame(done)))
  const fits = () => timeline.evaluate(box => box.scrollWidth <= box.clientWidth)
  for (let i = 0; i < ZOOMS; i++) {
    await page.locator('.zoombar i', { hasText: 'zoom_in' }).click()
    await drawn()
    if (await fits()) continue
    await page.locator('.zoombar i', { hasText: 'zoom_out' }).click()
    await drawn()
    break
  }
}

const projectName = name => `${name.replace(/-/g, ' ')} example`

// Example name -> its project.
const made = {}

// Known editor bugs: the viewer cannot draw these yet. Remove when fixed.
const NOT_YET = {
  animation: 'the template preview sends fxs as "[object Object]" (Preview.js urlfy)',
}

test.use({ video: 'off' })

test.describe('@screens', () => {
  test.use({ viewport: DESKTOP })

  test.beforeAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      await demoMedia(api, token)
      for (const example of examples()) {
        made[example.name] = await makeProject(
          api,
          token,
          projectName(example.name),
          editorClips(example.body)
        )
      }
    } finally {
      await api.dispose()
    }
  })

  test.afterAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      for (const project of Object.values(made)) {
        await api.delete(`/project/${project._id}`, auth(token))
      }
    } finally {
      await api.dispose()
    }
  })

  for (const example of examples()) {
    test(`screen: the ${example.name} example in the editor`, async ({ page }) => {
      test.fail(example.name in NOT_YET, NOT_YET[example.name])
      const file = screenFile('examples', example.name)
      clear(file)
      const project = made[example.name]
      await openProject(page, project)
      await arrange(page, { closing: ASIDE })
      await zoomToFit(page)

      // Playhead to the example's moment: a time-tool press on its clip.
      const at = moment(example)
      const clips = project.edl.clips
      const index = Math.max(
        0,
        clips.findIndex(clip => at < clip.start + clip.duration)
      )
      const along = (at - clips[index].start) / clips[index].duration
      const point = await onClip(page, index, along)
      await page.mouse.click(point.x, point.y)
      await expect.poll(() => playhead(page)).toBeCloseTo(at, 1)

      await save(page, file)
    })
  }
})
