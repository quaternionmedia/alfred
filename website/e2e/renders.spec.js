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
     */
    const renders = await (
      await request.get('/render', { headers: { Authorization: token } })
    ).json()
    const unfinished = renders.find(
      r => !r.destination && r.status !== 'RENDERED' && r.status !== 'UPLOADED'
    )
    test.skip(!unfinished, 'every render here has finished')

    await authedPage.goto('/#!/?stage=deliver')
    const row = authedPage
      .locator('.renderitem')
      .filter({ hasText: unfinished.project || unfinished.name || '' })
      .first()
    await expect(row.locator('button.deliver')).toBeDisabled()
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
