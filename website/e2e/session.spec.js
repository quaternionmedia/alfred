/**
 * The session lifecycle: renewal, expiry, logout, and what a token is worth.
 *
 * # Recipe: staying logged in, and stopping
 *
 * The editor keeps a JWT in sessionStorage and sends it as a bearer token.
 * Tokens live an hour, and `/auth/jwt/refresh` only exchanges one that still
 * works -- so the editor renews its token a few minutes before it expires, for
 * as long as somebody is using it, and again whenever the window comes back
 * into focus with more than half the token spent. A tab left alone for a whole
 * token lifetime is not renewed, and lapses.
 *
 * When the session does end -- the token ran out, or the server refused it --
 * the editor sends you to the login screen, and back to where you were once
 * you have logged in.
 *
 * It used to try to refresh *after* a request came back 401, by which time the
 * token it refreshed with had already been refused: that retry never renewed
 * anything, and every session simply ended an hour after login.
 *
 * The browser tests here move the page's clock rather than waiting an hour.
 * The server's clock does not move, which is the point: a token the page
 * believes is nearly spent is still good at the server, so renewing it works.
 */

const { test, expect, apiLogin, login, CREDENTIALS, SELECTORS } = require('./fixtures')

/** The claims of a bearer token, without verifying it. */
function claims(bearer) {
  const payload = bearer.split(' ').pop().split('.')[1]
  return JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'))
}

/** Resolves with the next renewal request the page sends. */
function nextRenewal(page) {
  return page.waitForRequest(
    r => r.method() == 'POST' && new URL(r.url()).pathname == '/auth/jwt/refresh'
  )
}

/** When the page believes its token expires (ms, on the page's clock).
 *
 * Asserted on rather than the token itself: the server's clock has not moved,
 * so a renewal within the same second as the login returns a byte-identical
 * JWT -- same subject, same `iat`, same `exp`. What a renewal changes for the
 * page is how long it has left.
 */
async function storedExpiry(page) {
  const stored = await page.evaluate(() => sessionStorage.getItem('alfred.jwt'))
  return stored ? JSON.parse(stored).expires_at : null
}

const MINUTE = 60 * 1000

/** Log back in from the login screen the session sent us to. */
async function logInAgain(page) {
  await page.locator('#username').fill(CREDENTIALS.username)
  await page.locator('#password').fill(CREDENTIALS.password)
  await page.locator('#submit').click()
}

test.describe('token refresh', () => {
  test('a valid token can be exchanged for a new one', async ({ request, token }) => {
    /**
     * This answered 500 for every caller.
     *
     * The route called `auth_backend.get_login_response(...)`, which has not
     * existed on fastapi-users' AuthenticationBackend for several major
     * versions -- it carries `login` and `logout` and nothing else.
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

  test('a token says how long it lives, in server time', async ({ request }) => {
    /**
     * `iat` beside `exp`, so the editor can count a token's lifetime down on
     * its own clock. Judged against `exp` alone, a browser running a few
     * minutes slow would renew a token that had already died.
     */
    const { iat, exp } = claims(await apiLogin(request))
    expect(Number.isInteger(iat), 'the token has no iat').toBe(true)
    expect(exp - iat).toBe(3600)
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

test.describe('staying logged in', () => {
  test('an editor in use renews its token before it expires', async ({ page }) => {
    // Logging in counts as use, so the first renewal is due five minutes
    // before the hour.
    await page.clock.install()
    await login(page)
    const before = await storedExpiry(page)

    const renewal = nextRenewal(page)
    await page.clock.fastForward('56:00')
    const res = await (await renewal).response()
    expect(res.status()).toBe(200)

    // A fresh hour from the moment of renewal, fifty-six minutes on.
    await expect.poll(() => storedExpiry(page)).toBeGreaterThan(before + 50 * MINUTE)
    await expect(page.locator(SELECTORS.login)).toHaveText(/logout/i)
  })

  test('coming back to the window renews a token more than half spent', async ({
    page,
  }) => {
    // Background tabs have their timers throttled, and a closed laptop lid
    // stops them, so returning is when a stale token is most likely.
    await page.clock.install()
    await login(page)

    const renewal = nextRenewal(page)
    await page.clock.fastForward('40:00')
    await page.evaluate(() => window.dispatchEvent(new Event('focus')))
    expect((await (await renewal).response()).status()).toBe(200)
  })

  test('a tab nobody uses is not renewed a second time', async ({ page }) => {
    // The first renewal rides on the login itself. After that, a token
    // lifetime with no input lets the session lapse: it ends within two
    // lifetimes of the last touch, not whenever the tab is closed.
    await page.clock.install()
    await login(page)
    const before = await storedExpiry(page)
    const first = nextRenewal(page)
    await page.clock.fastForward('56:00')
    await (await first).response()
    await expect.poll(() => storedExpiry(page)).toBeGreaterThan(before + 50 * MINUTE)

    const renewals = []
    page.on('request', r => {
      if (new URL(r.url()).pathname == '/auth/jwt/refresh') renewals.push(r)
    })
    await page.clock.fastForward('56:00')
    await page.clock.fastForward('05:00')

    await expect(page).toHaveURL(/#!\/login/)
    expect(renewals, 'an unused tab renewed its session').toEqual([])
  })

  test('a session that ran out while the machine slept goes to log in, and back', async ({
    page,
  }) => {
    await page.clock.install()
    await login(page)
    await page.goto('/#!/?stage=deliver')
    await expect(page.locator('#panel-deliver')).toBeVisible()

    // Two hours with the lid shut: the renewal is long overdue on waking,
    // and the token it would have renewed is already dead.
    await page.clock.fastForward('02:00:00')

    await expect(page).toHaveURL(/#!\/login\?redirect=/)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)

    await logInAgain(page)
    await expect(page).toHaveURL(/stage=deliver/)
  })

  test('a session the server refuses goes to log in, and back', async ({ page }) => {
    /**
     * Any 401: the token expired, or the server no longer accepts it -- a
     * restart with a new signing key, a disabled account. Renewal cannot
     * help, so the editor does not try; it keeps the route to come back to.
     */
    await login(page)
    await page.goto('/#!/?stage=render')
    await page.route(
      '**/project',
      route =>
        route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Unauthorized' }),
        }),
      { times: 1 }
    )
    await page.reload()

    await expect(page).toHaveURL(/#!\/login\?redirect=/)
    expect(
      await page.evaluate(() => sessionStorage.getItem('alfred.jwt')),
      'the refused token was kept'
    ).toBeNull()

    await logInAgain(page)
    await expect(page).toHaveURL(/stage=render/)
  })
})

test.describe('logout', () => {
  test('logout succeeds for an authenticated caller', async ({ request, token }) => {
    const res = await request.post('/auth/jwt/logout', {
      headers: { Authorization: token },
    })
    expect([200, 204]).toContain(res.status())
  })

  test('the editor logs out at the server, not at a route that does not exist', async ({
    page,
  }) => {
    /**
     * It posted to `/logout`, which is not a route; the static mount answered
     * 405 and nobody read it. It calls fastapi-users' own logout now, with the
     * token it is ending, and forgets the token whatever the answer.
     */
    await login(page)
    const posts = []
    page.on('request', r => {
      if (r.method() == 'POST') posts.push(new URL(r.url()).pathname)
    })
    const logout = page.waitForRequest(
      r => new URL(r.url()).pathname == '/auth/jwt/logout'
    )

    await page.locator(SELECTORS.login).click()

    expect((await logout).headers()['authorization']).toMatch(/^bearer /i)
    await expect(page.locator(SELECTORS.login)).toHaveText(/login/i)
    expect(posts).not.toContain('/logout')
    expect(await page.evaluate(() => sessionStorage.getItem('alfred.jwt'))).toBeNull()
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
