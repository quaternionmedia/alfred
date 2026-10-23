/**
 * The four-stage flow, end to end, against real data.
 *
 * Source -> Edit -> Render -> Deliver, driven through the UI, asserted against
 * the API. Nothing here is stubbed: the projects come from the seeded database,
 * the templates from the engine's own allowlist, and the delivery moves real
 * bytes to a real path.
 *
 * The render stage is the one place this stops short of the whole loop. Queuing
 * a render hands the job to a Celery worker and an actual encode, which takes
 * longer than a browser test should wait; these assert that the job is accepted
 * and recorded, and `test_render_pipeline.py` covers the encode itself with a
 * real 320x240 file.
 */

const { test, expect, holdTheRouter, releaseTheRouter } = require('./fixtures')

const DEMO = 'Timeline demo'

async function demoProject(request, token) {
  const res = await request.get('/project', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  return (await res.json()).find(p => p.name === DEMO)
}

/**
 * Routes the editor asks for that a server from before them does not have:
 * it answers 404, and the editor carries on without them (`GET /media` falls
 * back to `GET /videos`; no `GET /health` means nothing is said about the
 * renderer). Read from the server's own OpenAPI document, so a 404 from a
 * server that does have the route still fails the test.
 */
async function absentRoutes(request) {
  const paths = Object.keys(((await (await request.get('/openapi.json')).json()) || {}).paths || {})
  return ['/media', '/health'].filter(path => !paths.includes(path))
}

test.describe('the four-stage flow', () => {
  test('the timeline is the entry point', async ({ authedPage }) => {
    // `/` used to be a marketing homepage. The first thing the app shows is
    // now the thing it does.
    await authedPage.goto('/')
    await expect(authedPage.locator('#timeline')).toBeVisible()
    await expect(authedPage.locator('.stagerail')).toBeVisible()
  })

  test('the rail names all four stages in order', async ({ authedPage }) => {
    await authedPage.goto('/')
    const labels = await authedPage.locator('.stagerail .stage .stagelabel').allInnerTexts()
    expect(labels).toEqual(['Source', 'Edit', 'Render', 'Deliver'])
  })

  test('edit is the stage you land on', async ({ authedPage }) => {
    await authedPage.goto('/')
    await expect(authedPage.locator('#stage-edit')).toHaveClass(/active/)
  })

  test('the stage survives a reload, because it lives in the URL', async ({
    authedPage,
  }) => {
    // Mirroring the stage into a module variable did not survive a parameter
    // change, let alone a reload. Reading it from the route removed the copy
    // that could disagree.
    await authedPage.goto('/#!/?stage=deliver')
    await expect(authedPage.locator('#stage-deliver')).toHaveClass(/active/)
    await authedPage.reload()
    await expect(authedPage.locator('#stage-deliver')).toHaveClass(/active/)
  })

  test('stage 1 lists every project the API returns', async ({
    authedPage,
    request,
    token,
  }) => {
    const res = await request.get('/project', { headers: { Authorization: token } })
    const projects = await res.json()
    test.skip(projects.length === 0, 'no projects seeded in this environment')

    await authedPage.goto('/#!/?stage=source')
    await expect(authedPage.locator('.projectchoice')).toHaveCount(projects.length)
    for (const project of projects) {
      await expect(
        authedPage
          .locator('.projectpicker')
          .getByRole('button', { name: new RegExp(project.name, 'i') })
          .first()
      ).toBeVisible()
    }
  })

  test('choosing a project on stage 1 loads its timeline on stage 2', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The regression guard for the bug that making `/` the timeline exposed.
     *
     * The timeline loaded its project in `oninit` only. Once the timeline was
     * mounted at `/`, picking a project became a same-document navigation that
     * changed ?project= without remounting anything -- so the first project
     * opened was the only one that ever appeared, and no request was made.
     */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto('/#!/?stage=source')
    // Scoped to the project list. Material entries are buttons too, named
    // for their file, and a render is named after the project that produced
    // it -- so `Timeline demo` matches a project card and half a dozen
    // `Timeline demo_1280x720_....mp4` clips. Unscoped, `.first()` picked
    // whichever the page had drawn first, and the test failed about one run
    // in three with no change to the code under test.
    await authedPage
      .locator('.projectpicker')
      .getByRole('button', { name: new RegExp(DEMO, 'i') })
      .first()
      .click()

    await expect(authedPage).toHaveURL(new RegExp(`project=${demo._id}`))
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )
  })

  test('a stage chosen straight after a project keeps the project', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Choosing a stage on the rail changes the stage and keeps the rest of the
     * address, the project chosen a moment before included. The rail built
     * the new address from the router's route, which reads a change back a
     * tick after it is made; a stage chosen in that tick put back the address
     * from before the project, and the project was dropped. Here the tick is
     * held open, so the stage is chosen inside it every time.
     */
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto('/#!/?stage=source')
    const card = authedPage
      .locator('.projectpicker')
      .getByRole('button', { name: new RegExp(DEMO, 'i') })
      .first()
    await expect(card).toBeVisible()
    await holdTheRouter(authedPage)
    await card.click()
    await authedPage.locator('#stage-render').click()
    await releaseTheRouter(authedPage)

    // Mutation: build the address in `Flow.go` from `m.route.param()` -- the
    // project is dropped, and this fails.
    await expect(authedPage).toHaveURL(new RegExp(`project=${demo._id}`))
    await expect(authedPage).toHaveURL(/stage=render/)
    await expect(authedPage.locator('#stage-render')).toHaveClass(/active/)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(demo.edl.clips.length)
  })

  test('the timeline stays mounted across every stage', async ({
    authedPage,
    request,
    token,
  }) => {
    // The point of stages-of-one-view rather than four routes: the thing being
    // worked on does not disappear when you look at the settings for it.
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded')

    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      await authedPage.goto(`/#!/?project=${demo._id}&stage=${stage}`)
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(
        demo.edl.clips.length
      )
    }
  })

  test('stage 3 refuses to render an empty timeline', async ({ authedPage }) => {
    // No project selected means no clips, and a button that looks available
    // and then fails is worse than one that says why it is not.
    await authedPage.goto('/#!/?stage=render')
    await expect(authedPage.locator('#queue-render')).toBeDisabled()
    await expect(authedPage.getByText(/add a clip/i)).toBeVisible()
  })

  test('stage 3 offers the render when there is something to render', async ({
    authedPage,
    request,
    token,
  }) => {
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=render`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )
    await expect(authedPage.locator('#queue-render')).toBeEnabled()
  })

  test('stage 4 offers exactly what the server offers', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Built from `GET /destinations`, not hardcoded in the editor.
     *
     * Cloud delivery is the next phase, so the server currently offers only
     * `local` -- the one that needs no account, which is what makes "cloud
     * storage optional" true of getting your video back as well as making it.
     * Asserting against the endpoint rather than a literal means enabling
     * a destination is a server change, and this test follows it.
     */
    const offered = await (
      await request.get('/destinations', { headers: { Authorization: token } })
    ).json()
    expect(offered).toContain('local')

    await authedPage.goto('/#!/?stage=deliver')
    await expect(authedPage.locator('#destination')).toBeVisible()
    // The select is drawn before the list arrives: wait for the options,
    // rather than read them once at whatever moment the select appeared.
    await expect(authedPage.locator('#destination option')).toHaveCount(offered.length)
    const options = await authedPage.locator('#destination option').allInnerTexts()
    expect(options.sort()).toEqual([...offered].sort())
  })

  test('opening the flow makes no failing requests', async ({
    authedPage,
    request,
    token,
  }) => {
    const demo = await demoProject(request, token)
    test.skip(!demo, 'demo project not seeded')
    const absent = await absentRoutes(request)

    const failures = []
    authedPage.on('requestfinished', async req => {
      try {
        const res = await req.response()
        const path = new URL(req.url()).pathname
        if (res && res.status() === 404 && absent.includes(path)) return
        if (res && res.status() >= 400) {
          failures.push(`${res.status()} ${req.method()} ${path}`)
        }
      } catch (e) {
        // request objects can vanish mid-navigation
      }
    })

    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      await authedPage.goto(`/#!/?project=${demo._id}&stage=${stage}`)
      await authedPage.waitForTimeout(900)
    }

    expect(failures, `failing requests across the flow:\n${failures.join('\n')}`).toEqual(
      []
    )
  })
})

test.describe('delivery, with real bytes', () => {
  test('delivering a render always answers sensibly, never a 500', async ({
    request,
    token,
  }) => {
    /**
     * Driven through the API rather than the UI, because the UI can only
     * deliver a render a worker has already produced.
     *
     * This asserted 409-or-502 at first, on the assumption that a freshly
     * queued render has no file yet. That was true only while renders were
     * failing: a one-second solid colour now encodes in about a second, so the
     * file often exists by the time this runs and delivery succeeds. Asserting
     * the race made the test fail whenever the pipeline got faster, which is
     * the wrong direction for a test to point.
     *
     * What is true either way: the answer is a considered one. 200 when the
     * file is there, 409 when it is not yet, 502 if a destination refuses it --
     * and never a 500, which would mean the server broke rather than declined.
     * render-pipeline.spec.js covers the successful path deliberately, after
     * waiting for the encode.
     */
    const created = await request.post('/render', {
      headers: { Authorization: token },
      data: {
        edl: {
          clips: [
            {
              type: 'template',
              name: 'makeColor',
              duration: 1.0,
              data: { color: '#f2aa4c' },
            },
          ],
          duration: 1.0,
        },
        name: 'e2e delivery',
        project: 'e2e',
        width: 320,
        height: 180,
        duration: 1.0,
      },
    })
    expect(created.status()).toBe(200)
    const renderId = (await created.json()).replace(/"/g, '')

    const delivered = await request.post(`/render/${renderId}/deliver`, {
      headers: { Authorization: token },
    })
    expect(
      [200, 409, 502],
      `unexpected ${delivered.status()} from deliver: ${await delivered.text()}`
    ).toContain(delivered.status())
  })

  test('a malformed render id is refused, not crashed on', async ({
    request,
    token,
  }) => {
    const res = await request.post('/render/undefined/deliver', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(422)
  })

  test('an unknown destination is refused', async ({ request, token }) => {
    const res = await request.post(
      '/render/deadbeefdeadbeefdeadbeef/deliver?destination=dropbox',
      { headers: { Authorization: token } }
    )
    // 404 for the missing render is checked before the destination name, which
    // is the right order: there is nothing to deliver either way.
    expect([404, 502]).toContain(res.status())
  })

  test('delivery requires authentication', async ({ request }) => {
    const res = await request.post('/render/deadbeefdeadbeefdeadbeef/deliver')
    expect(res.status()).toBe(401)
  })
})
