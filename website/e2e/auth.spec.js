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

/**
 * A second account, for the one thing a single account cannot show: that its
 * projects are its own. Registered on demand, since a development stack takes
 * registrations; 400 means it already exists, which is just as good.
 */
const OTHER = {
  username: process.env.E2E_OTHER_EMAIL || 'other@mail.me',
  password: CREDENTIALS.password,
  name: 'other',
}

async function otherAccount(request) {
  const res = await request.post('/auth/register', {
    data: { email: OTHER.username, password: OTHER.password, first_name: OTHER.name },
  })
  expect([201, 400], await res.text()).toContain(res.status())
  return apiLogin(request, OTHER)
}

test.describe('project ownership', () => {
  test('a project you create is yours', async ({ request, token }) => {
    const res = await request.post('/project', {
      headers: { Authorization: token },
      data: { name: `owned ${test.info().workerIndex}`, logic: {} },
    })
    const project = await res.json()
    try {
      expect(project.owner).toBe(CREDENTIALS.username)
    } finally {
      await request.delete(`/project/${project._id}`, {
        headers: { Authorization: token },
      })
    }
  })

  test('another account can neither list nor open it', async ({ request, token }) => {
    /**
     * Any account could read, overwrite and delete any project. Somebody
     * else's project answers 404 now -- the same as one that does not exist,
     * so the answer does not confirm the id is real.
     */
    const other = await otherAccount(request)
    const project = await (
      await request.post('/project', {
        headers: { Authorization: token },
        data: { name: `private ${test.info().workerIndex}`, logic: {} },
      })
    ).json()

    try {
      const theirs = await (
        await request.get('/project', { headers: { Authorization: other } })
      ).json()
      expect(theirs.map(p => p._id)).not.toContain(project._id)

      for (const [method, path] of [
        ['get', `/project/${project._id}`],
        ['delete', `/project/${project._id}`],
      ]) {
        const res = await request[method](path, { headers: { Authorization: other } })
        expect(res.status(), `${method} ${path}`).toBe(404)
      }

      const still = await request.get(`/project/${project._id}`, {
        headers: { Authorization: token },
      })
      expect(still.status(), 'the other account removed it').toBe(200)
    } finally {
      await request.delete(`/project/${project._id}`, {
        headers: { Authorization: token },
      })
    }
  })
})
