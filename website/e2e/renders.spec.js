const { test, expect, SELECTORS } = require('./fixtures')

/**
 * Renders view.
 *
 * The Cypress suite's `render.js` had two live tests. Both navigated to
 * `/#!/renders` and asserted nothing -- every assertion in the file was
 * commented out, including the ones for preview and for render completion.
 * One of the two did not even log in first.
 *
 * What is converted here is the navigation, with assertions. What is *not*
 * converted is a render-completion test, because none existed to convert;
 * see the coverage notes in e2e/README.md.
 */
test.describe('renders', () => {
  test('renders view loads for an authenticated user', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/renders')
    await expect(authedPage).toHaveURL(/#!\/renders/)
    await expect(authedPage.locator(SELECTORS.renders)).toBeVisible()
  })

  test('render list is available from the API', async ({ request, token }) => {
    const res = await request.get('/render', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)
    expect(Array.isArray(await res.json())).toBe(true)
  })

  test('refuses renders to an anonymous caller', async ({ request }) => {
    const res = await request.get('/render')
    expect(res.status()).toBe(401)
  })
})
