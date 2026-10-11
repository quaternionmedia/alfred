/**
 * The session lifecycle: refresh, logout, and what a token is worth.
 *
 * # Recipe: staying logged in, and stopping
 *
 * The editor keeps a JWT in sessionStorage and sends it as a bearer token. When
 * a request comes back 401 the app tries `/auth/jwt/refresh` before giving up
 * and redirecting to the login screen -- so refresh is the only mechanism that
 * keeps anybody logged in past a token's lifetime, and it is worth testing at
 * the HTTP level rather than only through the UI.
 *
 * These are deliberately API-level. The browser path is covered in
 * views.spec.js ("a reload keeps the session"); what is checked here is the
 * contract the browser depends on.
 */

const { test, expect, apiLogin, CREDENTIALS } = require('./fixtures')

test.describe('token refresh', () => {
  test('a valid token can be exchanged for a new one', async ({ request, token }) => {
    /**
     * This answered 500 for every caller.
     *
     * The route called `auth_backend.get_login_response(...)`, which has not
     * existed on fastapi-users' AuthenticationBackend for several major
     * versions -- it carries `login` and `logout` and nothing else. So the one
     * path that exists to keep somebody logged in was the one path that could
     * not work, and a session reaching its expiry failed with a server error
     * rather than renewing.
     */
    const res = await request.post('/auth/jwt/refresh', {
      headers: { Authorization: token },
    })
    expect(res.status(), await res.text()).toBe(200)

    const body = await res.json()
    expect(body.access_token, 'refresh returned no token').toBeTruthy()
    expect(body.token_type).toBeTruthy()
  })

  test('the refreshed token actually authenticates', async ({ request, token }) => {
    // Returning a token-shaped thing is not the same as returning a working
    // one, and the difference is invisible until a session expires in front of
    // somebody.
    const refreshed = await (
      await request.post('/auth/jwt/refresh', { headers: { Authorization: token } })
    ).json()

    const me = await request.get('/users/me', {
      headers: { Authorization: `${refreshed.token_type} ${refreshed.access_token}` },
    })
    expect(me.status()).toBe(200)
    expect((await me.json()).email).toBe(CREDENTIALS.username)
  })

  test('refresh refuses an anonymous caller', async ({ request }) => {
    // Otherwise refresh is a way to mint a session without credentials.
    const res = await request.post('/auth/jwt/refresh')
    expect(res.status()).toBe(401)
  })

  test('refresh refuses a malformed token', async ({ request }) => {
    const res = await request.post('/auth/jwt/refresh', {
      headers: { Authorization: 'Bearer not-a-jwt' },
    })
    expect(res.status()).toBe(401)
  })
})

test.describe('logout', () => {
  test('logout succeeds for an authenticated caller', async ({ request, token }) => {
    const res = await request.post('/auth/jwt/logout', {
      headers: { Authorization: token },
    })
    expect([200, 204]).toContain(res.status())
  })

  test('a bearer token still works after logout', async ({ request }) => {
    /**
     * Pinned as a property, not filed as a defect.
     *
     * These are stateless JWTs with no server-side revocation list, so logging
     * out clears the browser's copy and cannot invalidate a token somebody
     * already holds. That is how the mechanism works and it is a real
     * consequence: a leaked token stays valid until it expires, and "log out
     * everywhere" is not something this design can offer.
     *
     * If revocation is ever added this test goes red, which is the moment to
     * decide deliberately rather than discover it.
     */
    const bearer = await apiLogin(request)

    await request.post('/auth/jwt/logout', { headers: { Authorization: bearer } })

    const me = await request.get('/users/me', { headers: { Authorization: bearer } })
    expect(
      me.status(),
      'a token was invalidated by logout -- revocation now exists, so this ' +
        'property has changed and the note above needs rewriting'
    ).toBe(200)
  })
})

test.describe('what a token gets you', () => {
  test('every gated route refuses an anonymous caller', async ({ request }) => {
    // One place that enumerates the closed doors. A route added without a
    // dependency is the failure this catches, and it is silent otherwise.
    const gated = ['/project', '/render', '/videos', '/templates', '/destinations', '/users/me']
    for (const path of gated) {
      const res = await request.get(path)
      expect(res.status(), `${path} answered anonymously`).toBe(401)
    }
  })

  test('a token from one login works across every gated route', async ({
    request,
    token,
  }) => {
    const gated = ['/project', '/render', '/videos', '/templates', '/destinations', '/users/me']
    for (const path of gated) {
      const res = await request.get(path, { headers: { Authorization: token } })
      expect(res.status(), `${path} refused a valid token`).toBe(200)
    }
  })

  test('the admin surface needs more than an ordinary session', async ({
    request,
    token,
  }) => {
    /**
     * The e2e user is not a superuser, so the admin router must refuse it.
     * A 200 here would mean any registered account can reach the admin
     * surface, which is the kind of thing that is only noticed deliberately.
     */
    const res = await request.post('/invoice', {
      headers: { Authorization: token },
      data: {},
    })
    expect([401, 403, 422]).toContain(res.status())
  })
})
