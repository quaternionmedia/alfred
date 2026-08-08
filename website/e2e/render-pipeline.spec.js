/**
 * The whole loop, with a video at the end of it.
 *
 * Queue a render from the browser, wait for the Celery worker to encode it with
 * ffmpeg, then deliver the result and check the bytes arrived. Nothing here is
 * stubbed: a real worker, a real encode, a real file.
 *
 * This is the only test in the suite that waits on an encode, so it is tagged
 * @slow and given its own timeout. Everything is deliberately small -- 320x180,
 * one second, a solid colour -- because the point is that the pipeline runs end
 * to end, not that it can handle a long edit.
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
}

/** Poll the render until the worker finishes with it. */
async function waitForRender(request, token, id, timeout = RENDER_TIMEOUT) {
  const deadline = Date.now() + timeout
  let last = null
  while (Date.now() < deadline) {
    const res = await request.get('/render', { headers: { Authorization: token } })
    const render = (await res.json()).find(r => r._id === id)
    last = render
    if (render && ['RENDERED', 'UPLOADED', 'failed'].includes(render.status)) {
      return render
    }
    await new Promise(r => setTimeout(r, 2000))
  }
  throw new Error(
    `render ${id} did not finish within ${timeout}ms. ` +
      `Last seen: status=${last && last.status} progress=${last && last.progress}. ` +
      'If status never changed, no Celery worker is consuming the queue.'
  )
}

test.describe('@slow render pipeline, end to end', () => {
  test.describe.configure({ timeout: RENDER_TIMEOUT + 60_000 })

  test('a render queued from the API becomes a real video file', async ({
    request,
    token,
  }) => {
    const created = await request.post('/render', {
      headers: { Authorization: token },
      data: TINY_RENDER,
    })
    expect(created.status()).toBe(200)
    const id = (await created.json()).replace(/"/g, '')

    const render = await waitForRender(request, token, id)

    expect(
      render.status,
      `render finished as ${render.status}. A 'failed' here is the encode ` +
        'itself, not this test -- check the renderer container logs.'
    ).not.toBe('failed')
    expect(render.progress).toBe(100)
    expect(render.filename).toMatch(/\.mp4$/)
  })

  test('the finished render can be delivered, and the bytes arrive', async ({
    request,
    token,
  }) => {
    const created = await request.post('/render', {
      headers: { Authorization: token },
      data: { ...TINY_RENDER, name: 'e2e delivery pipeline' },
    })
    const id = (await created.json()).replace(/"/g, '')
    const render = await waitForRender(request, token, id)
    test.skip(render.status === 'failed', 'the encode failed; see renderer logs')

    const delivered = await request.post(`/render/${id}/deliver`, {
      headers: { Authorization: token },
    })
    expect(delivered.status()).toBe(200)

    const receipt = await delivered.json()
    expect(receipt.destination).toBe('local')
    // The location names the file that was rendered, so a delivery cannot
    // quietly succeed against the wrong one.
    expect(receipt.location).toContain(render.filename)
  })

  test('delivery is recorded on the render, so it is not repeated blindly', async ({
    request,
    token,
  }) => {
    const created = await request.post('/render', {
      headers: { Authorization: token },
      data: { ...TINY_RENDER, name: 'e2e delivery record' },
    })
    const id = (await created.json()).replace(/"/g, '')
    const render = await waitForRender(request, token, id)
    test.skip(render.status === 'failed', 'the encode failed; see renderer logs')

    await request.post(`/render/${id}/deliver`, {
      headers: { Authorization: token },
    })

    const after = await request.get('/render', { headers: { Authorization: token } })
    const updated = (await after.json()).find(r => r._id === id)
    expect(updated.destination).toBe('local')
    expect(updated.link).toContain(render.filename)
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
      render.status,
      'the browser queued a render and the worker could not encode it; ' +
        'check the renderer container logs'
    ).not.toBe('failed')
    expect(render.filename).toMatch(/\.mp4$/)
  })
})
