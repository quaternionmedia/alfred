/**
 * Media in the editor: how long it runs, and how the browser fetches it.
 *
 * # Recipe: adding footage at its own length
 *
 * Choose a file on the Source stage (or press + beside it in the bin) and it
 * arrives as the whole file, from its start: as long as the file runs, which
 * the Source stage shows beside its name. A still image arrives as five
 * seconds of the picture, as does a file whose length the server could not
 * measure. Trimming stops at the end of the file. Every library clip used to
 * arrive as five seconds, because nothing reported a length.
 *
 * The server's media list (`GET /media`) carries, for each file, its kind,
 * its length and a short-lived signed URL. The viewer plays a video from that
 * URL by itself -- streaming, seeking -- instead of downloading the whole file
 * with the session first; renders download the same way. A server without
 * that list still works: names come from `GET /videos`, and files are fetched
 * with the session as before.
 *
 * The media list, the signed URLs and the render list are answered here: what
 * is under test is what the editor does with each answer.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

const RENDER_ID = '0123456789abcdef01234567'

/** Seconds since the epoch, `ahead` seconds from now: a signed URL's `exp`. */
const exp = ahead => Math.floor(Date.now() / 1000) + ahead
const signed = (path, ahead = 600) => `${path}?exp=${exp(ahead)}&sig=e2e-signature`

async function libraryNames(request, token) {
  const res = await request.get('/videos', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  return res.json()
}

/**
 * Answer `GET /media` from the real library's names, as the contract shapes
 * it: `entries(name)` returns what to say about each (merged over defaults).
 * Returns the list of answers given, so a test can see how often it was asked.
 */
async function serveMedia(page, request, token, entries = () => ({})) {
  const names = await libraryNames(request, token)
  const asked = []
  await page.route(
    url => url.pathname === '/media',
    async route => {
      const answer = names.map(name => ({
        name,
        kind: 'video',
        duration: 3,
        width: 320,
        height: 180,
        fps: 24,
        size: 1000,
        url: null,
        ...entries(name, asked.length),
      }))
      asked.push(answer)
      await route.fulfill({ json: answer })
    }
  )
  return { names, asked }
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

async function mediaProject(request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()
  return project
}

/**
 * Open `url` with every request going through the routes registered so far.
 *
 * The fixture has already loaded the app to log in, and it read the media
 * list then; the list is the page's own and is not asked for again. A reload
 * starts the page over -- the session is in sessionStorage, so it survives --
 * and only then does it go to `url`, so the page that read the old list never
 * opens what is under test.
 */
async function openFresh(page, url) {
  await page.reload()
  await page.goto(url)
}

/**
 * Record what the page hands the browser to download, instead of letting the
 * browser fetch it.
 *
 * A download from a link is fetched by the browser itself, outside the page:
 * no route sees it, so a test cannot answer it, and the real server would
 * refuse a signature made up here. What is under test is what the editor
 * hands over -- which link, and that it is left to the browser.
 */
async function recordDownloads(page) {
  await page.evaluate(() => {
    window.__downloads = []
    const click = HTMLAnchorElement.prototype.click
    HTMLAnchorElement.prototype.click = function () {
      if (this.hasAttribute('download') && !this.href.startsWith('blob:')) {
        window.__downloads.push({ href: this.href, download: this.getAttribute('download') })
        return
      }
      return click.call(this)
    }
  })
  return () => page.evaluate(() => window.__downloads)
}

const basename = name => String(name).split('/').pop()
const bars = names => names.find(n => n.includes('demo-bars'))

test.describe('a library clip is as long as its file', () => {
  test('it arrives at the length the server measured, from its start', async ({
    authedPage,
    request,
    token,
  }) => {
    const { names } = await serveMedia(authedPage, request, token, name =>
      name.includes('demo-bars') ? { duration: 7.5 } : {}
    )
    const sent = await captureRenders(authedPage)
    await openFresh(authedPage, '/#!/?stage=source')

    const choice = authedPage.locator(`.mediachoice[data-media="${bars(names)}"]`)
    // The length is shown beside the name: the length the clip arrives at.
    await expect(choice.locator('.mediaduration')).toHaveText('7.5 s')
    await choice.click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0]).toMatchObject({
      name: bars(names),
      type: 'video',
      inpoint: 0,
      outpoint: 7.5,
      duration: 7.5,
      start: 0,
    })
  })

  test('a file the server could not measure arrives as five seconds', async ({
    authedPage,
    request,
    token,
  }) => {
    const { names } = await serveMedia(authedPage, request, token, () => ({ duration: null }))
    const sent = await captureRenders(authedPage)
    await openFresh(authedPage, '/#!/?stage=source')

    const choice = authedPage.locator(`.mediachoice[data-media="${bars(names)}"]`)
    await expect(choice).toBeVisible()
    await expect(choice.locator('.mediaduration')).toHaveCount(0)
    await choice.click()
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0]).toMatchObject({ inpoint: 0, outpoint: 5, duration: 5 })
  })

  test('a still image arrives as a picture: a length and no window', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * It was sent as a video clip. otto draws an image clip as one picture
     * for as long as the clip lasts, with no in-point to move.
     */
    const { names } = await serveMedia(authedPage, request, token, name =>
      name.includes('demo-bars') ? { kind: 'image', duration: null } : {}
    )
    const sent = await captureRenders(authedPage)
    await openFresh(authedPage, '/#!/?stage=source')

    await authedPage.locator(`.mediachoice[data-media="${bars(names)}"]`).click()
    await expect(authedPage.locator('#timeline .clip.image')).toHaveCount(1)
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    const [still] = sent[0].edl.clips
    expect(still).toMatchObject({ type: 'image', name: bars(names), duration: 5, start: 0 })
    expect(still).not.toHaveProperty('inpoint')
    expect(still).not.toHaveProperty('outpoint')
  })

  test('a server without the media list: names from /videos, five seconds each', async ({
    authedPage,
  }) => {
    /**
     * Against a server from before `GET /media` -- it answers 404 -- the
     * editor reads the older list of names and carries on as it did.
     */
    let asked = 0
    await authedPage.route(
      url => url.pathname === '/media',
      route => {
        asked++
        return route.fulfill({ status: 404, json: { detail: 'Not Found' } })
      }
    )
    const sent = await captureRenders(authedPage)
    await openFresh(authedPage, '/#!/?stage=source')

    await authedPage.locator('.mediachoice[data-media*="demo-bars"]').click()
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0]).toMatchObject({ inpoint: 0, outpoint: 5, duration: 5 })
    // Asked once; the answer does not change by asking again.
    expect(asked).toBe(1)
  })
})

test.describe('a trim stops at the end of the file', () => {
  test('dragging past the end of the source leaves the clip as long as the file', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The shared fixture's video clip plays the first three seconds of
     * demo-bars. Served here as a 3.5-second file, a long drag to the right
     * lengthens the clip by half a second and no more.
     */
    const project = await mediaProject(request, token)
    await serveMedia(authedPage, request, token, name =>
      name.includes('demo-bars') ? { duration: 3.5 } : {}
    )
    const sent = await captureRenders(authedPage)
    await authedPage.route(
      url => url.pathname === `/project/${project._id}/settings`,
      route => route.fulfill({ json: project })
    )
    await openFresh(authedPage, `/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)

    await authedPage.locator('#TTools [data-tool="trim"]').click()
    const clip = authedPage.locator('#timeline .clip').first()
    const box = await clip.boundingBox()
    const y = box.y + box.height / 2
    await authedPage.mouse.move(box.x + box.width - 6, y)
    await authedPage.mouse.down()
    await authedPage.mouse.move(box.x + box.width + 300, y, { steps: 10 })
    await authedPage.mouse.up()

    await authedPage.locator('#render-timeline').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0]).toMatchObject({ inpoint: 0, outpoint: 3.5, duration: 3.5 })
    expect(sent[0].edl.clips[1].start).toBe(3.5)
  })
})

test.describe('media is fetched by signed URL', () => {
  test('the viewer plays a video from its signed URL, fetched by the browser', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The element is handed the signed URL and fetches it itself -- no
     * Authorization header, no blob: it streams, and nothing holds the
     * whole file in memory. (The request is passed on here with the session
     * added, so that a server which does not check signatures yet still
     * serves it.)
     */
    const project = await mediaProject(request, token)
    const [video] = project.edl.clips
    const url = signed(`/${video.name}`)
    await serveMedia(authedPage, request, token, name => (name === video.name ? { url } : {}))
    const fetched = []
    await authedPage.route(
      u => u.pathname === `/${video.name}`,
      async route => {
        const headers = route.request().headers()
        fetched.push({ url: route.request().url(), authorization: headers.authorization })
        await route.continue({ headers: { ...headers, authorization: token } })
      }
    )

    await openFresh(authedPage, `/#!/?project=${project._id}&stage=edit`)
    await authedPage.locator('#timeline .clip').first().click()

    const element = authedPage.locator('video.preview')
    await expect(element).toHaveAttribute('src', url, { timeout: 20_000 })
    await expect
      .poll(() => element.evaluate(v => v.readyState), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(2)
    expect(fetched.length).toBeGreaterThan(0)
    for (const request of fetched) {
      expect(request.url).toContain('sig=e2e-signature')
      expect(request.authorization, 'the browser sent the session with a signed URL').toBeUndefined()
    }
  })

  test('a signed URL that has run out is renewed, not handed to the viewer', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    const [video] = project.edl.clips
    const stale = signed(`/${video.name}`, -60)
    const fresh = signed(`/${video.name}`, 900)
    const { asked } = await serveMedia(authedPage, request, token, (name, n) =>
      name === video.name ? { url: n === 0 ? stale : fresh } : {}
    )
    const fetched = []
    await authedPage.route(
      u => u.pathname === `/${video.name}`,
      async route => {
        fetched.push(route.request().url())
        await route.continue({
          headers: { ...route.request().headers(), authorization: token },
        })
      }
    )

    await openFresh(authedPage, `/#!/?project=${project._id}&stage=edit`)
    await authedPage.locator('#timeline .clip').first().click()
    await expect(authedPage.locator('video.preview')).toHaveAttribute('src', fresh, {
      timeout: 20_000,
    })
    expect(asked.length).toBeGreaterThanOrEqual(2)
    expect(fetched.some(u => u.includes(`exp=${new URL(stale, 'http://x').searchParams.get('exp')}`)))
      .toBe(false)
  })

  test('a finished render downloads from its signed link', async ({ authedPage }) => {
    /**
     * # Recipe: downloading a render
     *
     * Download hands the browser the render's signed link: the browser
     * fetches the file straight to disk, under the name the server gives it,
     * the way any download goes -- instead of the page fetching the whole
     * file into memory with the session and handing it over afterwards.
     */
    const link = signed(`/render/${RENDER_ID}/download`)
    const viaSession = []
    await authedPage.route(
      url => url.pathname === '/render',
      route =>
        route.request().method() === 'GET'
          ? route.fulfill({ json: [renderDoc({ download_url: link })] })
          : route.fallback()
    )
    await authedPage.route(
      url => url.pathname === `/render/${RENDER_ID}/download`,
      route => {
        viaSession.push(route.request().url())
        return route.fulfill({ status: 500 })
      }
    )

    await openFresh(authedPage, '/#!/?stage=deliver')
    const handed = await recordDownloads(authedPage)
    const button = authedPage.locator(`.renderitem[data-render="${RENDER_ID}"] button.download`)
    await expect(button).toBeEnabled()
    await button.click()

    await expect.poll(handed).toEqual([
      // Named by the server's Content-Disposition, not by the page.
      { href: new URL(link, authedPage.url()).href, download: '' },
    ])
    expect(viaSession, 'the page fetched the file itself').toEqual([])
    await expect(authedPage.locator('#panel-deliver .stageerror')).toHaveCount(0)
  })

  test('a download link that has run out is asked for again', async ({ authedPage }) => {
    /**
     * The list was read when the stage opened; by the time Download is
     * pressed its link may have run out. A fresh one comes from the
     * render's status.
     */
    const stale = signed(`/render/${RENDER_ID}/download`, -30)
    const fresh = signed(`/render/${RENDER_ID}/download`, 900)
    await authedPage.route(
      url => url.pathname === '/render',
      route =>
        route.request().method() === 'GET'
          ? route.fulfill({ json: [renderDoc({ download_url: stale })] })
          : route.fallback()
    )
    await authedPage.route(
      url => url.pathname === `/render/${RENDER_ID}/status`,
      route =>
        route.fulfill({
          json: { id: RENDER_ID, state: 'rendered', status: 'RENDERED', progress: 100, download_url: fresh },
        })
    )

    await openFresh(authedPage, '/#!/?stage=deliver')
    const handed = await recordDownloads(authedPage)
    await authedPage
      .locator(`.renderitem[data-render="${RENDER_ID}"] button.download`)
      .click()
    await expect.poll(handed).toEqual([{ href: new URL(fresh, authedPage.url()).href, download: '' }])
  })
})

function renderDoc(overrides = {}) {
  return {
    _id: RENDER_ID,
    name: 'e2e signed render',
    project: 'e2e signed render',
    width: 320,
    height: 180,
    duration: 5,
    status: 'RENDERED',
    progress: 100,
    filename: `${RENDER_ID}.mp4`,
    destination: null,
    edl: { clips: [], duration: 5 },
    ...overrides,
  }
}
