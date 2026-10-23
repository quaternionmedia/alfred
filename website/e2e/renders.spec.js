const { test, expect } = require('./fixtures')

/**
 * Seeing and delivering renders.
 *
 * # Recipe: finding a finished render and sending it somewhere
 *
 * The renders table at `#!/renders` and the Deliver stage both listed
 * `/render`, fetched separately. The Deliver stage is the only one now, and it
 * carries what the table showed — project, size, duration, status and progress
 * — because a person on this stage is deciding which render to send, and that
 * decision depends on all of it.
 *
 * `#!/renders` redirects here.
 */
test.describe('the render list', () => {
  test('the old renders URL redirects into the flow', async ({ authedPage }) => {
    await authedPage.goto('/#!/renders')
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()
  })

  test('render list is available from the API', async ({ request, token }) => {
    const res = await request.get('/render', { headers: { Authorization: token } })
    expect(res.status()).toBe(200)
    expect(Array.isArray(await res.json())).toBe(true)
  })

  test('refuses renders to an anonymous caller', async ({ request }) => {
    const res = await request.get('/render')
    expect(res.status()).toBe(401)
  })

  test('each row shows the state of its render', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Status and progress lived only in the retired table, and they are what
     * tells you whether a render can be delivered at all. A row without them
     * makes the Deliver button a guess.
     */
    const renders = await (
      await request.get('/render', { headers: { Authorization: token } })
    ).json()
    test.skip(renders.length === 0, 'nothing rendered in this environment')

    await authedPage.goto('/#!/?stage=deliver')
    const first = authedPage.locator('.renderitem').first()
    await expect(first).toBeVisible()
    await expect(first.locator('.renderstatus')).toBeVisible()
  })

  test('an unfinished render cannot be delivered', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * There is no file to send until the worker has finished, and a button
     * that fails is worse than one that explains itself. The row disables it
     * and says why in the title.
     *
     * Asserted as a rule over one DOM snapshot, not by picking an unfinished
     * render from the API and then looking for its row. That version raced
     * the worker: other specs queue renders, so a render chosen as unfinished
     * could complete between the API read and the assertion, and the test
     * failed for having been right a moment earlier.
     *
     * The snapshot is taken once the list has arrived, with a render of the
     * test's own on it -- queued, rendering or done by then; the rule holds
     * for each. Taken at a fixed 300 ms, a list slower than that read as
     * nothing rendered, and the test skipped itself.
     */
    const queued = await request.post('/render', {
      headers: { Authorization: token },
      data: {
        edl: {
          clips: [
            { type: 'template', name: 'makeColor', duration: 1.0, data: { color: '#4c7af2' } },
          ],
          duration: 1.0,
        },
        name: 'e2e unfinished',
        project: 'e2e',
        width: 320,
        height: 180,
        duration: 1.0,
      },
    })
    expect(queued.status(), await queued.text()).toBe(200)
    const id = String(await queued.json()).replace(/"/g, '')

    await authedPage.goto('/#!/?stage=deliver')
    // The list has come, and been drawn, once it shows the render queued above.
    await expect(authedPage.locator(`.renderitem[data-render="${id}"]`)).toBeVisible()

    const rows = await authedPage.evaluate(() =>
      [...document.querySelectorAll('.renderitem')].map(row => {
        const deliver = row.querySelector('button.deliver')
        return {
          status: (row.querySelector('.renderstatus') || {}).textContent || '',
          deliverable: !(deliver || {}).disabled,
          why: deliver ? deliver.title : '',
          delivered: !!row.querySelector('.delivered'),
        }
      })
    )

    const FINISHED = /RENDERED|UPLOADED/i
    const wrong = rows.filter(
      r => !FINISHED.test(r.status) && !r.delivered && (r.deliverable || !/not finished/i.test(r.why))
    )

    expect(
      wrong,
      `renders not finished, offered for delivery or not saying why: ${JSON.stringify(wrong)}`
    ).toEqual([])
  })

  test('a delivered render says where it went', async ({
    authedPage,
    request,
    token,
  }) => {
    const renders = await (
      await request.get('/render', { headers: { Authorization: token } })
    ).json()
    const delivered = renders.find(r => r.destination)
    test.skip(!delivered, 'nothing delivered in this environment')

    await authedPage.goto('/#!/?stage=deliver')
    await expect(
      authedPage.locator('.delivered').first()
    ).toContainText(/delivered/)
  })
})
