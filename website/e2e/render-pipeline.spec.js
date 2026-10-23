/**
 * The whole loop, with a video at the end of it.
 *
 * Queue a render from the browser, wait for the Celery worker to encode it with
 * ffmpeg, then download and deliver the result and check the bytes arrived.
 * Nothing here is stubbed: a real worker, a real encode, a real file.
 *
 * This is the only spec in the suite that waits on an encode, so it is tagged
 * @slow and given its own timeout. Everything is deliberately small -- 320x180,
 * one second -- because the point is that the pipeline runs end to end, not
 * that it can handle a long edit.
 *
 * It also needs a worker. Where none is running the render never leaves
 * `queued`, so the wait below reports that plainly rather than timing out on an
 * assertion that says nothing.
 */

const { test, expect } = require('./fixtures')

// One second of video takes a few seconds to encode, plus Celery pickup. The
// generous ceiling is for a cold worker on a loaded machine.
const RENDER_TIMEOUT = 120_000

const TINY_RENDER = {
  edl: {
    clips: [
      {
        type: 'template',
        name: 'makeColor',
        duration: 1.0,
        start: 0.0,
        data: { color: '#f2aa4c' },
      },
    ],
    duration: 1.0,
  },
  name: 'e2e pipeline',
  project: 'e2e pipeline',
  width: 320,
  height: 180,
  fps: 24.0,
  duration: 1.0,
  quality: 'draft',
}

/**
 * Poll the render's own status until the worker finishes with it.
 *
 * `GET /render/{id}/status` rather than the whole list: the list is only the
 * caller's renders now, and the status route says `rendered` or `failed`
 * itself, with the reason when it failed.
 */
async function waitForRender(request, token, id, timeout = RENDER_TIMEOUT) {
  const deadline = Date.now() + timeout
  let last = null
  while (Date.now() < deadline) {
    const res = await request.get(`/render/${id}/status`, {
      headers: { Authorization: token },
    })
    expect(res.status(), `status of render ${id}`).toBe(200)
    last = await res.json()
    if (['rendered', 'failed'].includes(last.state)) return last
    await new Promise(r => setTimeout(r, 1000))
  }
  throw new Error(
    `render ${id} did not finish within ${timeout}ms. ` +
      `Last seen: state=${last && last.state} progress=${last && last.progress}. ` +
      'If it never left queued, no Celery worker is consuming the queue.'
  )
}

async function queue(request, token, body) {
  const created = await request.post('/render', {
    headers: { Authorization: token },
    data: body,
  })
  expect(created.status(), await created.text()).toBe(200)
  return (await created.json()).replace(/"/g, '')
}

/** An MP4 file starts with an `ftyp` box: four bytes of size, then the tag. */
function looksLikeMp4(bytes) {
  return bytes.length > 8 && bytes.subarray(4, 8).toString('latin1') === 'ftyp'
}

test.describe('@slow render pipeline, end to end', () => {
  test.describe.configure({ timeout: RENDER_TIMEOUT + 60_000 })

  test('a render queued from the API becomes a real video file', async ({
    request,
    token,
  }) => {
    const id = await queue(request, token, TINY_RENDER)

    const render = await waitForRender(request, token, id)

    expect(
      render.state,
      `the render failed: ${render.error}. A failure here is the encode ` +
        'itself, not this test -- check the renderer container logs.'
    ).toBe('rendered')
    expect(render.progress).toBe(100)
    // Named by the render's id alone: nothing from the request reaches the
    // filesystem path.
    expect(render.filename).toBe(`${id}.mp4`)
  })

  test('a clip from the media library renders', async ({ request, token }) => {
    /**
     * The defect this guards: a clip dragged from the media bin is named
     * `videos/<file>`, and the worker opened that against its own working
     * directory, where there is no `videos/`. Every render with a media clip
     * failed, and the only render test used a template, which needs no file.
     */
    const headers = { Authorization: token }
    const videos = await (await request.get('/videos', { headers })).json()
    const clip = videos.find(v => v.includes('demo-bars'))
    expect(clip, 'global setup generates demo media').toBeTruthy()

    const id = await queue(request, token, {
      ...TINY_RENDER,
      name: 'e2e library clip',
      edl: {
        clips: [
          {
            type: 'video',
            name: clip,
            duration: 1.0,
            start: 0.0,
            inpoint: 0.0,
            outpoint: 1.0,
            fadeIn: 0,
            fadeOut: 0,
          },
        ],
        duration: 1.0,
      },
    })

    const render = await waitForRender(request, token, id)
    expect(render.state, `the render failed: ${render.error}`).toBe('rendered')

    const download = await request.get(`/render/${id}/download`, { headers })
    expect(download.status()).toBe(200)
    expect(looksLikeMp4(await download.body())).toBe(true)
  })

  test('a finished render downloads, whole or in ranges', async ({
    request,
    token,
  }) => {
    const headers = { Authorization: token }
    const id = await queue(request, token, {
      ...TINY_RENDER,
      name: 'e2e download',
      project: 'e2e download',
    })
    const render = await waitForRender(request, token, id)
    test.skip(render.state === 'failed', `the encode failed: ${render.error}`)

    const whole = await request.get(`/render/${id}/download`, { headers })
    expect(whole.status()).toBe(200)
    expect(whole.headers()['content-type']).toBe('video/mp4')
    // Saved under a readable name, not the id.
    expect(whole.headers()['content-disposition']).toBe(
      'attachment; filename="e2e-download-320x180.mp4"'
    )
    const bytes = await whole.body()
    expect(looksLikeMp4(bytes)).toBe(true)
    expect(Number(whole.headers()['content-length'])).toBe(bytes.length)

    const part = await request.get(`/render/${id}/download`, {
      headers: { ...headers, Range: 'bytes=0-99' },
    })
    expect(part.status()).toBe(206)
    expect(part.headers()['content-range']).toBe(`bytes 0-99/${bytes.length}`)
    expect((await part.body()).equals(bytes.subarray(0, 100))).toBe(true)
  })

  test('the finished render can be delivered, and the link works', async ({
    request,
    token,
  }) => {
    const headers = { Authorization: token }
    const id = await queue(request, token, { ...TINY_RENDER, name: 'e2e delivery' })
    const render = await waitForRender(request, token, id)
    test.skip(render.state === 'failed', `the encode failed: ${render.error}`)

    const delivered = await request.post(`/render/${id}/deliver`, { headers })
    expect(delivered.status()).toBe(200)

    // A local delivery hands back the download route, not a path on the
    // server: the copy used to land under the public /data mount, and its
    // path was the link.
    const receipt = await delivered.json()
    expect(receipt).toEqual({
      destination: 'local',
      location: `/render/${id}/download`,
    })

    const followed = await request.get(receipt.location, { headers })
    expect(followed.status()).toBe(200)
    expect(looksLikeMp4(await followed.body())).toBe(true)
  })

  test('delivery is recorded on the render, so it is not repeated blindly', async ({
    request,
    token,
  }) => {
    const headers = { Authorization: token }
    const id = await queue(request, token, {
      ...TINY_RENDER,
      name: 'e2e delivery record',
    })
    const render = await waitForRender(request, token, id)
    test.skip(render.state === 'failed', `the encode failed: ${render.error}`)

    await request.post(`/render/${id}/deliver`, { headers })

    const status = await (
      await request.get(`/render/${id}/status`, { headers })
    ).json()
    expect(status.destination).toBe('local')

    const listed = (await (await request.get('/render', { headers })).json()).find(
      r => r._id === id
    )
    expect(listed.link).toBe(`/render/${id}/download`)
  })

  test('the browser can drive a render and see it appear', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The same loop, driven through the UI rather than the API.
     *
     * Queue from the Render stage, then watch the Deliver stage list it. This
     * is what "generate a video from the browser" means: no direct API call
     * for the part a person would do.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === 'Timeline demo')
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=render`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )

    // Keep it small: this queues a real encode on a real worker.
    await authedPage.locator('#render-width').fill('320')
    await authedPage.locator('#render-height').fill('180')

    const idsBefore = new Set(
      (
        await (
          await request.get('/render', { headers: { Authorization: token } })
        ).json()
      ).map(r => r._id)
    )

    await authedPage.locator('#queue-render').click()

    // Queuing moves to the Deliver stage, which is where the result shows up.
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()

    // Identify the render this click created, rather than counting.
    //
    // Counting was the first version and it passed while the render it queued
    // failed to encode -- the count goes up for a failed render just as
    // readily. The test reported that the browser can produce a video while no
    // video existed.
    let queuedId = null
    await expect
      .poll(
        async () => {
          const res = await request.get('/render', {
            headers: { Authorization: token },
          })
          const fresh = (await res.json()).find(r => !idsBefore.has(r._id))
          queuedId = fresh ? fresh._id : null
          return Boolean(fresh)
        },
        { timeout: 30_000, message: 'the browser did not queue a render' }
      )
      .toBe(true)

    const render = await waitForRender(request, token, queuedId)
    expect(
      render.state,
      `the browser queued a render and the worker could not encode it: ${render.error}`
    ).toBe('rendered')
    expect(render.filename).toBe(`${queuedId}.mp4`)
  })
})
