/**
 * The screenshots the docs open with, taken from the running app.
 *
 * # Screens
 *
 * Tagged `@screens` and run by the `docs` project beside the recipes:
 * `./al recipes` takes each one and saves it as
 * `docs/assets/screens/<name>.png`, which the README and the docs pages show
 * under their titles. Like a recipe's recording, a screenshot made this way
 * shows the app as it is: when a screen cannot be reached, its test fails and
 * its file is gone rather than stale.
 *
 * The state they show is built here, through the API, so they need no audio
 * engine and none of anyone's data: the demo media, a project made from it,
 * captions imported from a SubRip file and turned on, and one finished
 * render to deliver. The page's lists are narrowed to those, so a screen
 * taken on someone's own stack shows none of their projects, files or
 * renders.
 *
 * Desktop screens are 1280x800 and phone screens 390x844. Excluded from the
 * `chromium` and `phone` projects, like the recipes.
 */

const fs = require('fs')
const path = require('path')
const { test, expect, login } = require('./fixtures')

const SCREENS = path.join(__dirname, '..', '..', 'docs', 'assets', 'screens')

// The project every screen shows, made afresh on each run.
const PROJECT = 'Demo reel'

const SRT = `1
00:00:00,500 --> 00:00:02,800
A video editor in the browser

2
00:00:03,200 --> 00:00:05,800
Every frame is drawn by the server

3
00:00:06,200 --> 00:00:08,800
<i>Captions</i> from a subtitle file
`

const CAPTION_AT_FIVE = 'Every frame is drawn by the server'

// The demo media the project uses, of what `POST /demo/media` makes.
const DEMO_MEDIA = ['demo-bars.mp4', 'demo-colour.mp4', 'demo-testcard.mp4']

const RENDER_TIMEOUT = 120_000

const auth = token => ({ headers: { Authorization: token } })

/** The demo project: two demo clips between a title and a text box. */
async function makeProject(api, token) {
  const headers = auth(token)
  expect((await api.post('/demo/media', headers)).status()).toBe(200)
  const videos = (await (await api.get('/videos', headers)).json()).map(String)
  const clip = name => {
    const found = videos.find(video => video.endsWith(name))
    expect(found, `${name} is in the library`).toBeTruthy()
    return found
  }

  for (const old of (await (await api.get('/project', headers)).json()).filter(
    project => project.name === PROJECT
  )) {
    await api.delete(`/project/${old._id}`, headers)
  }

  const edl = {
    clips: [
      {
        type: 'template',
        name: 'title',
        duration: 3,
        start: 0,
        data: { text: 'Alfred', color: '#f2aa4c' },
      },
      { type: 'video', name: clip('demo-bars.mp4'), duration: 3, start: 3, inpoint: 0, outpoint: 3 },
      { type: 'video', name: clip('demo-testcard.mp4'), duration: 3, start: 6, inpoint: 0, outpoint: 3 },
      {
        type: 'template',
        name: 'textBox',
        duration: 3,
        start: 9,
        data: { text: 'Drama is life with the dull bits cut out.', color: '#f2aa4c' },
      },
    ],
    duration: 12,
  }
  const created = await api.post('/project', {
    ...headers,
    data: { name: PROJECT, logic: {}, fields: [], edl },
  })
  expect(created.status(), await created.text()).toBe(200)
  const project = await created.json()

  // Imported as the Captions panel imports a file, then saved and turned on.
  const imported = await api.post(`/project/${project._id}/captions/import`, {
    ...headers,
    data: { format: 'srt', text: SRT },
  })
  expect(imported.status(), await imported.text()).toBe(200)
  const { captions } = await imported.json()
  expect(captions).toHaveLength(3)
  const saved = await api.put(`/project/${project._id}/captions`, {
    ...headers,
    data: { captions, style: { enabled: true } },
  })
  expect(saved.status(), await saved.text()).toBe(200)

  return { ...project, edl }
}

/** One small render of it, finished, for the Deliver screen. */
async function renderProject(api, token, project) {
  const queued = await api.post('/render', {
    ...auth(token),
    data: {
      edl: project.edl,
      name: PROJECT,
      project: PROJECT,
      project_id: project._id,
      width: 640,
      height: 360,
      fps: 24,
      duration: project.edl.duration,
      quality: 'draft',
    },
  })
  expect(queued.status(), await queued.text()).toBe(200)
  const id = (await queued.json()).replace(/"/g, '')
  await expect
    .poll(
      async () =>
        (await (await api.get(`/render/${id}/status`, auth(token))).json()).state,
      {
        message: 'the render finished; is a render worker running?',
        timeout: RENDER_TIMEOUT,
        intervals: [1000],
      }
    )
    .toMatch(/rendered|failed/)
  const status = await (await api.get(`/render/${id}/status`, auth(token))).json()
  expect(status.state, status.error).toBe('rendered')
  return id
}

/**
 * Narrow the page's lists to what this spec made.
 *
 * The projects, the media library and the renders are the stack's, and on
 * someone's own stack they are that person's: a screenshot taken there would
 * publish them. Each list is fetched from the server as usual and answered
 * with only the demo's entries, so every stack takes the same screens.
 */
async function onlyTheDemo(page) {
  const demo = {
    '/project': entry => entry._id === project._id,
    '/media': entry => DEMO_MEDIA.some(name => String(entry.name).endsWith(name)),
    '/videos': entry => DEMO_MEDIA.some(name => String(entry).endsWith(name)),
    '/render': entry => entry.project_id === project._id,
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

/** Save the page as `docs/assets/screens/<name>.png`, once it has settled. */
async function save(page, name) {
  await page.waitForLoadState('networkidle')
  // Every picture on the page drawn, the preview's included.
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.images].every(image => image.complete && image.naturalWidth > 0)
      )
    )
    .toBe(true)
  // The pointer off the page, so nothing is drawn hovered.
  await page.mouse.move(-1, -1)
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(SCREENS, `${name}.png`),
    animations: 'disabled',
    caret: 'hide',
    // The notices the test's own login raised, which a person at this
    // screen would not see.
    style: '.alertify-notifier { display: none !important; }',
  })
}

/** A screen's file goes first, so a screen that fails leaves none behind. */
function clear(name) {
  fs.rmSync(path.join(SCREENS, `${name}.png`), { force: true })
}

let project
let render

// Stills: the docs project records everything else.
test.use({ video: 'off' })

test.describe('@screens', () => {
  test.describe.configure({ timeout: RENDER_TIMEOUT + 60_000 })
  test.use({ viewport: { width: 1280, height: 800 } })

  test.beforeAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      project = await makeProject(api, token)
      render = await renderProject(api, token, project)
    } finally {
      await api.dispose()
    }
  })

  // The stack left as the screens found it.
  test.afterAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      if (render) await api.delete(`/render/${render}`, auth(token))
      if (project) await api.delete(`/project/${project._id}`, auth(token))
    } finally {
      await api.dispose()
    }
  })

  /** The demo on `stage`, its timeline drawn.
   *
   * Narrowed before logging in: the page fetches its lists as the session
   * starts, not again when a stage is chosen.
   */
  const open = async (page, stage) => {
    await onlyTheDemo(page)
    await login(page)
    await page.goto(`/#!/?project=${project._id}&stage=${stage}`)
    await expect(page.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
  }

  /** The playhead on the title, which shows its frame and its settings. */
  const onTheTitle = async page => {
    await page.locator('#timeline .clip').first().click()
    await expect(page.locator('img.preview')).toBeVisible()
  }

  /** The playhead five seconds in: the colour bars, under the second caption. */
  const onTheBars = async page => {
    await page.evaluate(() => document.activeElement && document.activeElement.blur())
    await page.keyboard.press('ArrowRight')
    await expect(page.locator('#caption-overlay')).toHaveText(CAPTION_AT_FIVE)
  }

  test('screen: the workspace at Edit', async ({ page }) => {
    clear('edit')
    await open(page, 'edit')
    await onTheTitle(page)
    await save(page, 'edit')
  })

  test('screen: captions over the picture', async ({ page }) => {
    clear('captions')
    await open(page, 'edit')
    await page.locator('#paneltab-captions').click()
    await expect(page.locator('#captions-list .captionrow')).toHaveCount(3)
    await onTheBars(page)
    await save(page, 'captions')
  })

  test('screen: Render', async ({ page }) => {
    clear('render')
    await open(page, 'render')
    await onTheBars(page)
    await expect(page.locator('#queue-render')).toBeEnabled()
    await save(page, 'render')
  })

  test('screen: Deliver', async ({ page }) => {
    clear('deliver')
    await open(page, 'deliver')
    await onTheTitle(page)
    await expect(page.locator('#panel-deliver')).toContainText(PROJECT)
    await expect(page.locator('#panel-deliver')).toContainText('rendered')
    await save(page, 'deliver')
  })

  test('screen: the Panels menu', async ({ page }) => {
    clear('panels-menu')
    await open(page, 'edit')
    await onTheTitle(page)
    // One panel closed, so the menu has one to bring back.
    await page.locator('#paneltab-template .lm_close_tab').click()
    await page.locator('#panels-button').click()
    await expect(page.locator('#panels-menu')).toBeVisible()
    await save(page, 'panels-menu')
  })

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 } })

    test('screen: Edit on a phone', async ({ page }) => {
      clear('phone-edit')
      await open(page, 'edit')
      await expect(page.locator('#panel-captions')).toBeVisible()
      await onTheBars(page)
      await save(page, 'phone-edit')
    })

    test('screen: Render on a phone', async ({ page }) => {
      clear('phone-render')
      await open(page, 'render')
      await onTheBars(page)
      await expect(page.locator('#queue-render')).toBeEnabled()
      // The stage's panel scrolls inside itself, above the viewer: down to
      // its button.
      await page.locator('#queue-render').scrollIntoViewIfNeeded()
      await save(page, 'phone-render')
    })
  })
})
