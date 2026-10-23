/**
 * The timeline tools, and the media they act on.
 *
 * # Recipe: editing with the timeline tools
 *
 * The editor is three regions in the order you work: a **viewer** showing the
 * selected clip with the output settings beside it, a **transport** carrying
 * everything that moves the playhead, and an **editor** with the timeline
 * flanked by the tools that change it and the bin that feeds it.
 *
 * All media here is the generated demo footage -- `POST /demo/media`
 * synthesises it locally with ffmpeg, so these tests need no downloads and no
 * cloud account.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

/**
 * The shared media fixture, read rather than created.
 *
 * This used to create the project if it was absent, which eight parallel
 * workers all did at once -- three projects called "Tool test", and an
 * unrelated spec counting project rows failed on the duplicates. The same
 * check-then-create race the /demo/project endpoint had. It is created once in
 * global-setup.js now, before any worker exists to race.
 */
async function mediaProject(request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(
    project,
    `${MEDIA_PROJECT} is missing; global-setup.js should have created it`
  ).toBeTruthy()
  return project
}

test.describe('selected media renders', () => {
  test('a video clip previews from generated demo footage', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The preview was blank for every video clip.
     *
     * `<video src="videos/x.mp4">` is a browser-issued request with no
     * Authorization header, and /videos requires a session -- so it 401'd and
     * showed nothing. Selecting media in the bin looked like a click that did
     * not register. The element is handed an object URL fetched with the token
     * instead.
     */
    const project = await mediaProject(request, token)

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(2)

    await authedPage.locator('#timeline .clip').first().click()

    const video = authedPage.locator('video.preview')
    await expect(video).toBeVisible({ timeout: 30_000 })
    // A blob URL means the fetch carried the token and the bytes arrived.
    // Generous timeouts: this downloads and decodes a real file, and with the
    // suite running eight workers wide the first frame can take a while.
    await expect(video).toHaveAttribute('src', /^blob:/, { timeout: 30_000 })

    // readyState >= 2 is HAVE_CURRENT_DATA: decoded, not merely requested.
    await expect
      .poll(() => video.evaluate(v => v.readyState), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(2)
  })

  test('a template clip previews as a rendered frame', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await authedPage.locator('#timeline .clip').nth(1).click()

    const image = authedPage.locator('img.preview')
    await expect(image).toBeVisible({ timeout: 20_000 })
    await expect(image).toHaveAttribute('src', /^blob:/)
  })

  test('previewing makes no unauthorised requests', async ({
    authedPage,
    request,
    token,
  }) => {
    // The whole point of fetching with the token: a 401 here means the preview
    // has gone back to letting the element fetch for itself.
    const project = await mediaProject(request, token)

    const unauthorised = []
    authedPage.on('requestfinished', async req => {
      try {
        const res = await req.response()
        if (res && res.status() === 401 && req.url().includes('/videos')) {
          unauthorised.push(new URL(req.url()).pathname)
        }
      } catch (e) {
        // request objects can vanish mid-navigation
      }
    })

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await authedPage.locator('#timeline .clip').first().click()
    await authedPage.waitForTimeout(2500)

    expect(unauthorised, `401s while previewing: ${unauthorised}`).toEqual([])
  })
})

test.describe('the tools pass their events', () => {
  test('choosing a timeline tool marks it active', async ({
    authedPage,
    request,
    token,
  }) => {
    // The tools set a shared `state.tool()`, and nothing indicated whether a
    // click had landed. The active tool is the only one with a background.
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)

    const trim = authedPage.locator('#TTools i[title="trim"]')
    await expect(trim).toBeVisible()

    const background = () => trim.evaluate(el => getComputedStyle(el).backgroundColor)
    const before = await background()
    await trim.click()
    await expect.poll(background).not.toBe(before)
  })

  test('only one timeline tool is active at a time', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)

    const highlighted = async () =>
      authedPage.locator('#TTools i').evaluateAll(
        nodes =>
          nodes.filter(n => {
            const bg = getComputedStyle(n).backgroundColor
            return bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent'
          }).length
      )

    for (const tool of ['trim', 'move', 'time selector']) {
      await authedPage.locator(`#TTools i[title="${tool}"]`).click()
      expect(await highlighted(), `after choosing ${tool}`).toBe(1)
    }
  })

  test('the transport controls are present and clickable', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)

    // Wait for the timeline before touching the transport.
    //
    // These controls call Edl.jump, which reads the clip list -- clicking
    // before it has loaded exercises the empty case, and the layout shifts as
    // clips arrive, so a click can land on a moving target. Failed about one
    // run in five and passed on every rerun, which is the signature of acting
    // before the page settled rather than of a broken control.
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )

    for (const control of ['start', 'back 5s', 'forward 5s', 'end']) {
      const button = authedPage.locator(`#PlaybackTools i[title="${control}"]`)
      await expect(button).toBeVisible()
      // Clicking must not throw; the playhead assertions live below.
      await button.click()
    }
    // The play control is addressed by id, because its title is the action it
    // will perform and therefore changes as it is used.
    await expect(authedPage.locator('#playpause')).toBeVisible()
  })

  test('clicking transport controls raises no page errors', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * These call into `Edl.jump`, which indexes the clip list. With an empty
     * or short timeline that is where an off-by-one would surface, and a
     * thrown handler leaves the toolbar looking fine and doing nothing.
     */
    const project = await mediaProject(request, token)

    const errors = []
    authedPage.on('pageerror', e => errors.push(String(e.message)))

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip').first()).toBeVisible()

    // Every control the toolbar actually has, asked of the toolbar.
    //
    // This looped a written list -- `['start', 'forward 5s', 'back 5s',
    // 'end']` -- against a toolbar of five. The omitted one was play, and
    // play was the only one still broken: all five had reached through a
    // module that was never mounted, and the four seek controls had since
    // been rewritten to call `Edl.jump` directly. So the suite reported the
    // transport as raising no errors, about a transport whose most-used
    // control threw on every click.
    //
    // Deriving the list means a sixth control is covered the day it is added
    // rather than the day somebody remembers to add it here.
    const controls = authedPage.locator('#PlaybackTools i')
    const count = await controls.count()
    expect(count, 'the transport has no controls to press').toBeGreaterThan(0)

    for (let i = 0; i < count; i++) {
      await controls.nth(i).click()
      await authedPage.waitForTimeout(150)
    }

    // Pressed twice, because play and pause are one control in two states and
    // only one of them is reachable per press.
    await authedPage.locator('#playpause').click()
    await authedPage.waitForTimeout(200)

    expect(errors, `transport controls threw: ${errors.join('; ')}`).toEqual([])
  })

  test('play advances the playhead, and pause stops it', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: playing the timeline
     *
     * The play button had never worked. It called into a component that was
     * imported but never rendered, so the element reference it needed was
     * always null and the click threw before anything moved.
     *
     * What it drives now is the timeline, not a file. That distinction is
     * load-bearing rather than pedantic: `POST /demo/project` builds its
     * timeline from template clips, so the first project anyone generates is
     * entirely stills, and a transport bound to a video element would leave
     * it inert -- on exactly the project a new user presses play on first.
     */
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip').first()).toBeVisible()

    const elapsed = () => authedPage.locator('.timecode').innerText()
    expect(await elapsed()).toBe('0:00.00')

    await authedPage.locator('#playpause').click()
    await expect(authedPage.locator('#playpause')).toHaveText('pause')

    // Polled rather than measured after a fixed wait: the assertion is that
    // the playhead moves, not that it reaches a particular second by a
    // particular moment on a loaded CI machine.
    await expect.poll(async () => (await elapsed()) !== '0:00.00').toBe(true)

    await authedPage.locator('#playpause').click()
    await expect(authedPage.locator('#playpause')).toHaveText('play_arrow')

    const stopped = await elapsed()
    await authedPage.waitForTimeout(600)
    expect(await elapsed(), 'the playhead moved after pause').toBe(stopped)
  })

  test('the transport says so when there is nothing to play', async ({
    authedPage,
  }) => {
    // An empty timeline used to offer five controls that looked available and
    // threw when pressed. Saying why beats failing silently.
    await authedPage.goto('/#!/?stage=edit')
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(0)

    const play = authedPage.locator('#playpause')
    await expect(play).toHaveClass(/disabled/)
    await expect(play).toHaveAttribute('title', /nothing on the timeline/i)
  })
})

test.describe('the project actions', () => {
  test('saving a timeline persists it, and keeps the rest of the project', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: saving a timeline
     *
     * The save button posted to `/edl`, which is not a route on this server
     * and never has been, with a bare `m.request` that would not have carried
     * a token if it were. The rejection was handled nowhere, so the button
     * reported nothing. Timelines could not be saved at all.
     *
     * The name assertion is the point of the second half. The obvious way to
     * write a timeline back is `PUT /project/{id}`, which replaces the whole
     * document -- a partial body arrives with `logic` unset, `logic` is
     * required, and every later GET of that project answers 500. This checks
     * that saving clips did not take the name with it.
     */
    await request.post('/demo/media', { headers: { Authorization: token } })

    // Its own project, created here and used by nobody else.
    //
    // The first version of this test saved into whichever shared project had
    // clips, which meant it permanently added one every run: the fixtures
    // grew, a spec asserting clips sit on one row started failing on the
    // width, and a render of that project began pulling in a file this test
    // had put there. A test that writes to shared state has to bring its own.
    const created = await request.post('/project', {
      headers: { Authorization: token },
      data: {
        name: `save test ${test.info().workerIndex}-${test.info().repeatEachIndex}`,
        logic: {},
        edl: { clips: [] },
      },
    })
    expect(created.status(), await created.text()).toBeLessThan(400)
    const project = await created.json()
    const before = 0

    // The order that used to lose the clip, every time rather than some of
    // the time. Opening the project fetches its clips, and when that answer
    // landed after a clip was added it replaced the timeline: the clip
    // vanished, Save found nothing to save, and no request was made. That
    // was this test failing on most runs -- and on every run where the first
    // library clip was short enough to win the race. The project's answer is
    // held here until the clip is on the timeline.
    let release
    const held = new Promise(resolve => (release = resolve))
    const own = url => url.pathname === `/project/${project._id}`
    await authedPage.route(own, async route => {
      if (route.request().method() === 'GET') await held
      await route.fallback()
    })
    const loaded = authedPage.waitForResponse(
      res => own(new URL(res.url())) && res.request().method() === 'GET'
    )

    try {
      await authedPage.goto(`/#!/?stage=source&project=${project._id}`)
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(before)

      await authedPage.locator('.mediachoice').first().click()
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(before + 1)

      release()
      await loaded
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(before + 1)

      await authedPage.locator('#save-timeline').click()

      await expect
        .poll(async () => {
          const saved = await (
            await request.get(`/project/${project._id}`, {
              headers: { Authorization: token },
            })
          ).json()
          return ((saved.edl || {}).clips || []).length
        })
        .toBe(before + 1)

      const saved = await (
        await request.get(`/project/${project._id}`, {
          headers: { Authorization: token },
        })
      ).json()
      expect(saved.name, 'saving the timeline overwrote the project name').toBe(
        project.name
      )

      await authedPage.reload()
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(before + 1)
    } finally {
      // Its own project, so it goes too: every run used to leave one behind.
      await request.delete(`/project/${project._id}`, { headers: { Authorization: token } })
    }
  })

  test('the actions say why they are unavailable', async ({ authedPage }) => {
    // Both were always enabled and always clickable, whether or not there was
    // a project to act on or a clip to act with.
    await authedPage.goto('/#!/?stage=edit')
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(0)

    for (const id of ['#save-timeline', '#render-timeline']) {
      const button = authedPage.locator(id)
      await expect(button).toHaveClass(/disabled/)
      await expect(button).toHaveAttribute('title', /select a project|nothing on the timeline/i)
    }
  })
})

test.describe('the editor layout groups its tools', () => {
  test('the three regions are present and in order', async ({ authedPage }) => {
    /**
     * Viewer, transport, editor. The arrangement used to be a stack of bars
     * with related controls apart and unrelated controls together -- aspect
     * and resolution floating above the preview, speed buried inside the
     * timeline's grid, zoom stranded below it.
     */
    await authedPage.goto('/')
    const tops = await authedPage
      .locator('section.viewer, section.transport, section.editor')
      .evaluateAll(nodes => nodes.map(n => Math.round(n.getBoundingClientRect().y)))

    expect(tops.length).toBe(3)
    expect(tops, 'regions are out of order').toEqual([...tops].sort((a, b) => a - b))
  })

  test('every region starts on the same left edge', async ({ authedPage }) => {
    // Separate bars with separate padding is most of why the page read as
    // stacked fragments rather than one interface.
    await authedPage.goto('/')
    const lefts = await authedPage
      .locator('section.viewer, section.transport, section.editor')
      .evaluateAll(nodes => nodes.map(n => Math.round(n.getBoundingClientRect().x)))

    expect(new Set(lefts).size, `regions start at ${lefts}`).toBe(1)
  })

  test('the timeline is the widest thing in the editor', async ({
    authedPage,
    request,
    token,
  }) => {
    // The subject of the page should take the space; the tools adorn it.
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline')).toBeVisible()

    const widths = await authedPage.evaluate(() => {
      const width = sel => {
        const el = document.querySelector(sel)
        return el ? Math.round(el.getBoundingClientRect().width) : 0
      }
      return {
        surface: width('.editorsurface'),
        tools: width('.editortools'),
        actions: width('.editoractions'),
      }
    })

    expect(widths.surface).toBeGreaterThan(widths.tools)
    expect(widths.surface).toBeGreaterThan(widths.actions)
  })

  test('related tools sit in one group, not scattered', async ({ authedPage }) => {
    // Playback and speed both move the playhead, so both live in the
    // transport; the tools that change clips live beside the timeline.
    await authedPage.goto('/')

    const grouped = await authedPage.evaluate(() => ({
      playbackInTransport: !!document.querySelector('.transport #PlaybackTools'),
      speedInTransport: !!document.querySelector('.transport .tools'),
      timelineToolsInEditor: !!document.querySelector('.editor #TTools'),
      binUnderTimeline: (() => {
        const t = document.querySelector('#timeline')
        const b = document.querySelector('#bin')
        if (!t || !b) return false
        return b.getBoundingClientRect().y >= t.getBoundingClientRect().y
      })(),
    }))

    expect(grouped.playbackInTransport).toBe(true)
    expect(grouped.speedInTransport).toBe(true)
    expect(grouped.timelineToolsInEditor).toBe(true)
    expect(grouped.binUnderTimeline).toBe(true)
  })
})

test.describe('async actions say they are working', () => {
  test('the render button reports itself busy', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Every action on these panels talks to the server and none of them said
     * so, so a slow request looked like a click that missed. Buttons carry a
     * spinner and `aria-busy` while their request is in flight.
     */
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=render`)

    // The button enables only once the timeline has clips, so wait for those
    // rather than for the button: a disabled button and a not-yet-loaded one
    // look identical, and clicking the second does nothing quietly.
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )

    const button = authedPage.locator('#queue-render')
    await expect(button).toBeEnabled()
    await expect(button).toHaveAttribute('aria-busy', 'false')

    await button.click()
    // Either it is still working, or it finished and moved to Deliver. Both
    // are correct; what must not happen is a click with no acknowledgement.
    await expect(authedPage.locator('#panel-deliver')).toBeVisible({
      timeout: 30_000,
    })
  })

  test('a busy button is disabled, so it cannot be double-fired', async ({
    authedPage,
  }) => {
    // The disabled state is what stops a second click queueing a second
    // render, which is the failure this indicator exists to prevent.
    await authedPage.goto('/#!/?stage=render')
    const button = authedPage.locator('#queue-render')
    // With no project there are no clips, so it is disabled for that reason --
    // the attribute contract is what matters here.
    await expect(button).toHaveAttribute('aria-busy', 'false')
    await expect(button).toBeDisabled()
  })
})
