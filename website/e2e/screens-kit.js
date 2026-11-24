/**
 * Shared by screens-examples.spec.js and screens-tools.spec.js.
 * Same rules as screens.spec.js: demo media only, lists narrowed, file cleared first.
 */

const fs = require('fs')
const path = require('path')
const { expect, login } = require('./fixtures')

const SCREENS = path.join(__dirname, '..', '..', 'docs', 'assets', 'screens')

// What `POST /demo/media` makes, 3 s each.
const DEMO_MEDIA = ['demo-bars.mp4', 'demo-colour.mp4', 'demo-testcard.mp4']

const DESKTOP = { width: 1280, height: 800 }

const auth = token => ({ headers: { Authorization: token } })

/** Make the demo media; answer the library's name for each file. */
async function demoMedia(api, token) {
  expect((await api.post('/demo/media', auth(token))).status()).toBe(200)
  const videos = (await (await api.get('/videos', auth(token))).json()).map(String)
  return Object.fromEntries(
    DEMO_MEDIA.map(name => {
      const found = videos.find(video => video.endsWith(name))
      expect(found, `${name} is in the library`).toBeTruthy()
      return [name, found]
    })
  )
}

/** A project `name` holding `clips`, replacing any of that name. */
async function makeProject(api, token, name, clips) {
  for (const old of (await (await api.get('/project', auth(token))).json()).filter(
    project => project.name === name
  )) {
    await api.delete(`/project/${old._id}`, auth(token))
  }
  const duration = clips.reduce((sum, clip) => sum + clip.duration, 0)
  const created = await api.post('/project', {
    ...auth(token),
    data: { name, logic: {}, fields: [], edl: { clips, duration } },
  })
  expect(created.status(), await created.text()).toBe(200)
  return created.json()
}

/** List only `projects` and the demo media, so no one's own data is shot.
 * Call before login: the lists load as the session starts. */
async function narrow(page, projects) {
  const ids = new Set(projects.map(project => project._id))
  const demo = {
    '/project': entry => ids.has(entry._id),
    '/media': entry => DEMO_MEDIA.some(name => String(entry.name).endsWith(name)),
    '/videos': entry => DEMO_MEDIA.some(name => String(entry).endsWith(name)),
    '/render': entry => ids.has(entry.project_id),
  }
  await page.route(
    url => Object.hasOwn(demo, url.pathname),
    async route => {
      if (route.request().method() !== 'GET') return route.fallback()
      const response = await route.fetch()
      const listed = await response.json()
      const keep = demo[new URL(route.request().url()).pathname]
      await route.fulfill({
        response,
        json: Array.isArray(listed) ? listed.filter(keep) : listed,
      })
    }
  )
}

/** `project` on the Edit stage, its timeline drawn. */
async function openProject(page, project) {
  await narrow(page, [project])
  await login(page)
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await expect(page.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
}

/** Close the panels `closing`, then zoom the timeline in `zooms` times.
 * Wider clips show their in- and out-points. */
async function arrange(page, { closing = [], zooms = 0 } = {}) {
  for (const id of closing) await page.locator(`#paneltab-${id} .lm_close_tab`).click()
  for (const id of closing) await expect(page.locator(`#paneltab-${id}`)).toHaveCount(0)
  const zoomIn = page.locator('.zoombar i', { hasText: 'zoom_in' })
  for (let i = 0; i < zooms; i++) await zoomIn.click()
}

/** The playhead, in seconds, from the timecode. */
async function playhead(page) {
  const [minutes, seconds] = (await page.locator('.timecode').innerText()).split(':')
  return Number(minutes) * 60 + Number(seconds)
}

/** A point `along` clip `index` (0 start, 1 end), scrolled on screen. */
async function onClip(page, index, along = 0.5) {
  const clip = page.locator('#timeline .clip').nth(index)
  await clip.scrollIntoViewIfNeeded()
  const box = await clip.boundingBox()
  return { x: box.x + box.width * along, y: box.y + box.height / 2, box }
}

/** `docs/assets/screens/<group>/<name>.png` */
const screenFile = (group, name) => path.join(SCREENS, group, `${name}.png`)

/** Remove first: a screen that fails leaves no stale file. */
function clear(file) {
  fs.rmSync(file, { force: true })
}

/** Save the page once previews, pictures and videos have settled. */
async function save(page, file) {
  await page.waitForLoadState('networkidle')
  await expect(page.locator('.preview.loading, .preview.busy')).toHaveCount(0)
  await expect(page.locator('.preview.unrenderable'), 'the viewer drew its clip').toHaveCount(0)
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.images].every(image => image.complete && image.naturalWidth > 0)
      )
    )
    .toBe(true)
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.querySelectorAll('video')].every(
          video => video.readyState >= 2 && !video.seeking
        )
      )
    )
    .toBe(true)
  // Pointer off the page: nothing drawn hovered.
  await page.mouse.move(-1, -1)
  await page.waitForTimeout(400)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  await page.screenshot({
    path: file,
    animations: 'disabled',
    caret: 'hide',
    // The login's own notices.
    style: '.alertify-notifier { display: none !important; }',
  })
}

module.exports = {
  DEMO_MEDIA,
  DESKTOP,
  arrange,
  auth,
  clear,
  demoMedia,
  makeProject,
  narrow,
  onClip,
  openProject,
  playhead,
  save,
  screenFile,
}
