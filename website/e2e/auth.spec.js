const { test, expect, apiLogin, CREDENTIALS } = require('./fixtures')

/**
 * API-level auth.
 *
 * This is the content the Cypress suite's `auth.js` intended to cover. That
 * file was 74 lines of entirely commented-out code, built around seeding
 * `localStorage` with a user object -- which the app never reads. These tests
 * exercise the API directly instead, which needs no such shortcut.
 */
test.describe('auth API', () => {
  test('rejects an unauthenticated request for the current user', async ({
    request,
  }) => {
    const res = await request.get('/users/me')
    expect(res.status()).toBe(401)
  })

  test('rejects login with a wrong password', async ({ request }) => {
    const res = await request.post('/auth/jwt/login', {
      form: { username: CREDENTIALS.username, password: 'definitely-wrong' },
    })
    expect(res.status()).toBe(400)
  })

  test('issues a bearer token for valid credentials', async ({ request }) => {
    const res = await request.post('/auth/jwt/login', {
      form: {
        username: CREDENTIALS.username,
        password: CREDENTIALS.password,
      },
    })
    expect(res.status()).toBe(200)

    const body = await res.json()
    expect(body).toHaveProperty('access_token')
    expect(body.token_type.toLowerCase()).toBe('bearer')
  })

  test('accepts that token for the current user', async ({ request }) => {
    const token = await apiLogin(request)

    const res = await request.get('/users/me', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)

    const me = await res.json()
    expect(me.email).toBe(CREDENTIALS.username)
  })

  test('lists projects for an authenticated caller', async ({
    request,
    token,
  }) => {
    const res = await request.get('/project', {
      headers: { Authorization: token },
    })
    expect(res.status()).toBe(200)
    expect(Array.isArray(await res.json())).toBe(true)
  })

  test('refuses to list projects without a token', async ({ request }) => {
    const res = await request.get('/project')
    expect(res.status()).toBe(401)
  })
})
