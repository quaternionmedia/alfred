/**
 * Following a render from queued to delivered.
 *
 * # Recipe: watching a render finish
 *
 * Queue a render and the Deliver stage follows it: the row moves from queued
 * to rendering with a progress bar, then to rendered -- or to failed, with the
 * reason. Nothing needs reloading. It used to be a snapshot of the moment the
 * stage opened, so a render looked queued for as long as you watched it.
 *
 * The status and download routes are answered here rather than by a worker:
 * what is under test is what the page does with each answer, and a real encode
 * cannot be made to pause at 40% on cue. render-pipeline.spec.js drives the
 * real thing end to end.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

const RENDER_ID = '0123456789abcdef01234567'

function renderDoc(overrides = {}) {
  return {
    _id: RENDER_ID,
    name: 'e2e watched render',
    project: 'e2e watched render',
    width: 320,
    height: 180,
    duration: 5,
    status: null,
    progress: 0,
    filename: `${RENDER_ID}.mp4`,
    destination: null,
    edl: { clips: [], duration: 5 },
    ...overrides,
  }
}

/** A canned sequence: each call returns the next answer, then the last one again. */
function sequence(answers) {
  let calls = 0
  const next = () => answers[Math.min(calls++, answers.length - 1)]
  next.calls = () => calls
  return next
}

/**
 * Serve the render endpoints from canned answers.
 *
 * `list` and `status` are sequences; a status answer with `httpStatus` is sent
 * as an error with that code.
 */
async function serveRenders(page, { list, status }) {
  await page.route(
    url => url.pathname === '/render',
    async route => {
      const method = route.request().method()
      if (method === 'POST') {
        return route.fulfill({ json: RENDER_ID })
      }
      if (method === 'GET') return route.fulfill({ json: list() })
      return route.fallback()
    }
  )
  await page.route(
    url => url.pathname === `/render/${RENDER_ID}/status`,
    async route => {
      const answer = status()
      if (answer.httpStatus) {
        return route.fulfill({
          status: answer.httpStatus,
          json: { detail: answer.detail || 'Not Found' },
        })
      }
      return route.fulfill({ json: { id: RENDER_ID, ...answer } })
    }
  )
}

async function queueFromRenderStage(page, request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()
  // The stage remembers the size on the project; keep the fixture as it is.
  await page.route(
    url => url.pathname === `/project/${project._id}/settings`,
    route => route.fulfill({ json: project })
  )

  await page.goto(`/#!/?project=${project._id}&stage=render`)
  await expect(page.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
  await page.locator('#queue-render').click()
  await expect(page.locator('#panel-deliver')).toBeVisible()
  return page.locator(`.renderitem[data-render="${RENDER_ID}"]`)
}

test.describe('a queued render is followed until it settles', () => {
  test('the row moves from queued, through progress, to rendered', async ({
    authedPage,
    request,
    token,
  }) => {
    const status = sequence([
      { state: 'queued', status: null, progress: null },
      { state: 'rendering', status: null, progress: 40 },
      { state: 'rendering', status: null, progress: 40 },
      { state: 'rendered', status: 'RENDERED', progress: 100, filename: `${RENDER_ID}.mp4` },
    ])
    await serveRenders(authedPage, { list: sequence([[renderDoc()]]), status })

    const row = await queueFromRenderStage(authedPage, request, token)

    await expect(row).toHaveAttribute('data-state', 'rendering')
    await expect(row.locator('.renderprogress')).toHaveText('40%')
    await expect(row.locator('progress.renderbar')).toHaveJSProperty('value', 40)

    await expect(row).toHaveAttribute('data-state', 'rendered')
    await expect(row.locator('.renderstatus')).toHaveText('rendered')
    await expect(row.locator('button.deliver')).toBeEnabled()
    await expect(row.locator('progress.renderbar')).toHaveCount(0)

    // Settled means settled: nothing keeps asking.
    const asked = status.calls()
    await authedPage.waitForTimeout(2500)
    expect(status.calls(), 'still polling a finished render').toBe(asked)
  })

  test('a failed render says why, and the words stay words', async ({
    authedPage,
    request,
    token,
  }) => {
    const reason = 'ffmpeg exited with status 1: <b>no such filter</b>'
    await serveRenders(authedPage, {
      list: sequence([[renderDoc()]]),
      status: sequence([
        { state: 'rendering', status: null, progress: 10 },
        { state: 'failed', status: 'failed', progress: 10, error: reason },
      ]),
    })

    const row = await queueFromRenderStage(authedPage, request, token)

    await expect(row).toHaveAttribute('data-state', 'failed')
    await expect(row.locator('.rendererror')).toHaveText(reason)
    await expect(row.locator('button.deliver')).toBeDisabled()
    // The notification is HTML; the reason must not be.
    const toast = authedPage.locator('.ajs-message.ajs-error').filter({ hasText: 'failed' })
    await expect(toast).toContainText(reason)
    await expect(toast.locator('b')).toHaveCount(0)
  })

  test('without a status route, the render list is read instead', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The status route is new. Against a server that predates it -- 404 --
     * the page falls back to the render list rather than giving up, and asks
     * the missing route only once.
     */
    const status = sequence([{ httpStatus: 404 }])
    await serveRenders(authedPage, {
      status,
      // Every list read advances this -- the stage's own loads as well as the
      // watcher's -- so 55% is held for several reads to stay observable.
      list: sequence([
        [renderDoc()],
        [renderDoc({ progress: 55 })],
        [renderDoc({ progress: 55 })],
        [renderDoc({ progress: 55 })],
        [renderDoc({ progress: 55 })],
        [renderDoc({ status: 'RENDERED', progress: 100 })],
      ]),
    })

    const row = await queueFromRenderStage(authedPage, request, token)

    await expect(row).toHaveAttribute('data-state', 'rendering')
    await expect(row.locator('.renderprogress')).toHaveText('55%')
    await expect(row).toHaveAttribute('data-state', 'rendered')
    expect(status.calls()).toBe(1)
  })

  test('a render already on the list keeps moving while the stage is open', async ({
    authedPage,
  }) => {
    /**
     * Not queued from this page -- another tab, the form, before a reload --
     * so nothing is watching it by id. The stage refreshes its list while
     * anything on it is unfinished.
     */
    const status = sequence([{ httpStatus: 404 }])
    await serveRenders(authedPage, {
      status,
      list: sequence([
        [renderDoc({ progress: 20 })],
        [renderDoc({ progress: 70 })],
        [renderDoc({ status: 'UPLOADED', progress: 100 })],
      ]),
    })

    await authedPage.goto('/#!/?stage=deliver')
    const row = authedPage.locator(`.renderitem[data-render="${RENDER_ID}"]`)
    await expect(row).toHaveAttribute('data-state', 'rendering')
    await expect(row.locator('.renderprogress')).toHaveText('70%')
    await expect(row).toHaveAttribute('data-state', 'rendered')
    // The list served it; nothing asked the status route about a render this
    // page did not queue.
    expect(status.calls()).toBe(0)
  })
})
