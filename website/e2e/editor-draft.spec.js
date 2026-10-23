/**
 * An unsaved timeline outlives the page that made it.
 *
 * # Recipe: getting unsaved edits back
 *
 * Edits to a project's timeline are kept in the tab until they are saved. If
 * the page is reloaded, or the session runs out and you log in again, opening
 * the project offers them back: **Restore them** puts the unsaved timeline on
 * screen, **Discard** keeps the saved one. Saving clears what was kept. It is
 * the tab's own, and goes when the tab does.
 *
 * Every edit since the last save used to be lost, with no warning, whenever
 * the page went away.
 *
 * These open the shared media project and never save it: what a test keeps
 * stays in its own browser, and the one test that saves brings its own
 * project.
 */

const { test, expect, CREDENTIALS, MEDIA_PROJECT } = require('./fixtures')

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

const clips = page => page.locator('#timeline .clip')
const offer = page => page.locator('#draft-offer')

/** Open `project` on the Edit stage, its saved clips on screen. */
async function open(page, project) {
  // Rendering from the toolbar would remember a size on the shared fixture.
  await page.route(
    url => url.pathname === `/project/${project._id}/settings`,
    route => route.fulfill({ json: project })
  )
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await expect(clips(page)).toHaveCount(project.edl.clips.length)
}

/** Add a title card from the bin, changed to say `text`. */
async function addTitle(page, text) {
  await page.locator('#bin .binclip[data-bin-name="title"] .binadd').click()
  await page.locator('#param-text').fill(text)
  await expect(page.locator('#timeline .clip.template[name="title"]')).toHaveText(text)
}

test.describe('an unsaved timeline outlives a reload', () => {
  test('after a reload the unsaved timeline is offered back, and restored', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await open(authedPage, project)
    await addTitle(authedPage, 'Not saved yet')

    await authedPage.reload()
    // The saved timeline is what loads; the unsaved one is offered.
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)
    await expect(offer(authedPage)).toContainText('unsaved changes')
    await expect(offer(authedPage)).toContainText(`${project.edl.clips.length + 1} clips`)

    await authedPage.locator('#draft-restore').click()
    await expect(offer(authedPage)).toHaveCount(0)
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length + 1)
    await expect(authedPage.locator('#timeline .clip.template[name="title"]')).toHaveText(
      'Not saved yet'
    )

    // Restored is restored: it is what a render receives.
    const sent = await captureRenders(authedPage)
    await authedPage.locator('#render-timeline').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips.map(c => c.name)).toEqual([
      ...project.edl.clips.map(c => c.name),
      'title',
    ])
    expect(sent[0].edl.clips.at(-1).data.text).toBe('Not saved yet')
  })

  test('discarded, it is gone, and the saved timeline stays', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await open(authedPage, project)
    await addTitle(authedPage, 'Throw this away')

    await authedPage.reload()
    await expect(offer(authedPage)).toBeVisible()
    await authedPage.locator('#draft-discard').click()
    await expect(offer(authedPage)).toHaveCount(0)
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)

    // And it is not offered again.
    await authedPage.reload()
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)
    await authedPage.waitForTimeout(500)
    await expect(offer(authedPage)).toHaveCount(0)
  })

  test('a timeline that was only looked at offers nothing', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Opening a project, selecting clips and playing them changes nothing,
     * so nothing is kept -- and a stored `start` or fade, which the editor
     * would send differently, is not counted as a change.
     */
    const project = await mediaProject(request, token)
    await open(authedPage, project)
    await clips(authedPage).nth(1).click()
    await authedPage.waitForTimeout(800)

    await authedPage.reload()
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)
    await authedPage.waitForTimeout(500)
    await expect(offer(authedPage)).toHaveCount(0)
  })

  test('saving clears what was kept', async ({ authedPage, request, token }) => {
    const created = await request.post('/project', {
      headers: { Authorization: token },
      data: {
        name: `draft test ${test.info().workerIndex}-${test.info().repeatEachIndex}`,
        logic: {},
        edl: { clips: [] },
      },
    })
    expect(created.status(), await created.text()).toBeLessThan(400)
    const project = await created.json()
    try {
      await open(authedPage, { ...project, edl: { clips: [] } })
      await addTitle(authedPage, 'Saved now')
      await authedPage.locator('#save-timeline').click()
      await expect
        .poll(async () => {
          const saved = await (
            await request.get(`/project/${project._id}`, { headers: { Authorization: token } })
          ).json()
          return ((saved.edl || {}).clips || []).length
        })
        .toBe(1)

      await authedPage.reload()
      await expect(clips(authedPage)).toHaveCount(1)
      await authedPage.waitForTimeout(500)
      await expect(offer(authedPage)).toHaveCount(0)
    } finally {
      await request.delete(`/project/${project._id}`, { headers: { Authorization: token } })
    }
  })
})

test.describe('an unsaved timeline outlives the session', () => {
  test('when the session ends, logging in again offers it back', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The server refusing the session sends the page to log in, carrying
     * where it was; the timeline goes with the page. Logging in again comes
     * back to the project, and offers what was unsaved.
     */
    const project = await mediaProject(request, token)
    await open(authedPage, project)
    await addTitle(authedPage, 'Kept through a login')

    // The session ends: the next request is refused.
    let refused = false
    await authedPage.route(
      url => url.pathname === '/render',
      route => {
        if (refused || route.request().method() !== 'GET') return route.fallback()
        refused = true
        return route.fulfill({ status: 401, json: { detail: 'Unauthorized' } })
      }
    )
    await authedPage.locator('#stage-deliver').click()
    await expect(authedPage).toHaveURL(/#!\/login/)

    await authedPage.locator('#username').fill(CREDENTIALS.username)
    await authedPage.locator('#password').fill(CREDENTIALS.password)
    await authedPage.locator('#submit').click()

    await expect(authedPage).toHaveURL(new RegExp(`project=${project._id}`))
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)
    await expect(offer(authedPage)).toBeVisible()
    await authedPage.locator('#draft-restore').click()
    await expect(authedPage.locator('#timeline .clip.template[name="title"]')).toHaveText(
      'Kept through a login'
    )
  })
})

test.describe('storage that refuses', () => {
  test('a browser that will not keep the timeline still edits it', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Private browsing and full quotas refuse storage outright. The editor
     * goes on working; there is simply nothing to offer back.
     */
    const errors = []
    authedPage.on('pageerror', e => errors.push(String(e.message)))
    await authedPage.addInitScript(() => {
      const setItem = Storage.prototype.setItem
      Storage.prototype.setItem = function (key, value) {
        if (String(key).startsWith('alfred.draft.')) throw new Error('QuotaExceededError')
        return setItem.call(this, key, value)
      }
    })
    const project = await mediaProject(request, token)
    // The refusal is installed for pages loaded from now on.
    await authedPage.reload()
    await open(authedPage, project)
    await addTitle(authedPage, 'Nowhere to keep this')
    await authedPage.waitForTimeout(800)

    await authedPage.reload()
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)
    await authedPage.waitForTimeout(500)
    await expect(offer(authedPage)).toHaveCount(0)
    expect(errors).toEqual([])
  })
})
