/**
 * What a render request may ask for, and whose renders a caller can reach.
 *
 * # Recipe: the render API's promises
 *
 * Asserted at the HTTP level against the running stack. None of this waits on
 * an encode, so it needs no worker: every request here is refused, or answered,
 * before the worker would be involved.
 *
 * - Media is named as `GET /videos` lists it, or by URL on an allowed host;
 *   anything else is a 422 before anything is stored (contract C4).
 * - Encoding comes from a named quality preset; client ffmpeg options are a
 *   422 (C5).
 * - `GET /render/{id}/status` answers for one render (C2), with a signed
 *   `download_url` once there is a file to download (M1).
 * - A render is its owner's: another user gets 404 for it everywhere (C6).
 * - The download takes a session or a signature for exactly its own path,
 *   and nothing else (M1).
 */

const { test, expect, CREDENTIALS } = require('./fixtures')

const TEMPLATE = {
  type: 'template',
  name: 'makeColor',
  duration: 1.0,
  start: 0.0,
  data: { color: '#101820' },
}

function renderBody(clips, extra = {}) {
  return {
    edl: { clips, duration: 1.0 },
    name: 'e2e render api',
    project: 'e2e render api',
    width: 64,
    height: 48,
    ...extra,
  }
}

test.describe('a render request is checked before it is queued', () => {
  const refusedMedia = [
    ['an absolute path', '/etc/hostname'],
    ['a path out of the library', 'videos/../.secret_key'],
    ['a backslash', 'videos\\demo-bars.mp4'],
    ['a file URL', 'file:///etc/hostname'],
    ['a URL on a host nobody allowed', 'http://169.254.169.254/latest/meta-data/'],
    ['a file the library does not have', 'videos/no-such-file.mp4'],
  ]

  for (const [what, name] of refusedMedia) {
    test(`media named by ${what} is a 422`, async ({ request, token }) => {
      const res = await request.post('/render', {
        headers: { Authorization: token },
        data: renderBody([{ type: 'video', name, duration: 1.0, start: 0.0 }]),
      })
      expect(res.status()).toBe(422)
      const refused = await res.json()
      expect(refused.detail).toContain('clip 1')
      // What a client switches on, beside the sentence (docs/api/errors.md).
      expect(refused.code).toBe('edl_refused')
    })
  }

  test('media named as the library lists it is accepted', async ({
    request,
    token,
  }) => {
    const headers = { Authorization: token }
    const videos = await (await request.get('/videos', { headers })).json()
    const clip = videos.find(v => v.includes('demo-'))
    expect(clip, 'global setup generates demo media').toBeTruthy()

    const res = await request.post('/render', {
      headers,
      data: renderBody([{ type: 'video', name: clip, duration: 1.0, start: 0.0 }], {
        quality: 'draft',
      }),
    })
    expect(res.status()).toBe(200)
  })

  test('a template outside the allowlist is a 422', async ({ request, token }) => {
    const res = await request.post('/render', {
      headers: { Authorization: token },
      data: renderBody([{ ...TEMPLATE, name: 'rgbToDec' }]),
    })
    expect(res.status()).toBe(422)
    expect((await res.json()).code).toBe('edl_refused')
  })

  test('the EDL preview checks the same things', async ({ request, token }) => {
    const res = await request.post('/preview/?t=0', {
      headers: { Authorization: token },
      data: renderBody([{ type: 'video', name: '/etc/hostname', duration: 1.0 }]),
    })
    expect(res.status()).toBe(422)
  })

  for (const [extra, code] of [
    [{ ffmpeg_params: ['-b:v', '25M'] }, 'encoder_options_refused'],
    [{ bitrate: ['5000k'] }, 'encoder_options_refused'],
    [{ quality: 'TV' }, 'unknown_quality'],
  ]) {
    test(`encoder options are not the client's: ${JSON.stringify(extra)}`, async ({
      request,
      token,
    }) => {
      const res = await request.post('/render', {
        headers: { Authorization: token },
        data: renderBody([TEMPLATE], extra),
      })
      expect(res.status()).toBe(422)
      const refused = await res.json()
      expect(refused.detail).toContain('draft')
      expect(refused.code).toBe(code)
    })
  }
})

test.describe('a render answers for itself', () => {
  test('its status has exactly the contract fields', async ({ request, token }) => {
    const headers = { Authorization: token }
    const created = await request.post('/render', {
      headers,
      data: renderBody([TEMPLATE], { quality: 'draft' }),
    })
    const id = (await created.json()).replace(/"/g, '')

    const res = await request.get(`/render/${id}/status`, { headers })
    expect(res.status()).toBe(200)
    const status = await res.json()
    expect(Object.keys(status).sort()).toEqual(
      [
        'destination',
        'download_url',
        'error',
        'filename',
        'id',
        'progress',
        'state',
        'status',
      ].sort()
    )
    expect(status.id).toBe(id)
    expect(status.filename).toBe(`${id}.mp4`)
    expect(['queued', 'rendering', 'rendered', 'failed']).toContain(status.state)
    // A URL only once there is a finished file behind it.
    if (status.state !== 'rendered') expect(status.download_url).toBeNull()
  })

  test('a malformed id is a 422 and a missing one a 404', async ({
    request,
    token,
  }) => {
    const headers = { Authorization: token }
    for (const route of ['status', 'download']) {
      expect((await request.get(`/render/undefined/${route}`, { headers })).status()).toBe(422)
      expect(
        (await request.get(`/render/deadbeefdeadbeefdeadbeef/${route}`, { headers })).status()
      ).toBe(404)
    }
  })

  test('none of it is open to an anonymous caller', async ({ request }) => {
    for (const route of ['status', 'download']) {
      const res = await request.get(`/render/deadbeefdeadbeefdeadbeef/${route}`)
      expect(res.status()).toBe(401)
    }
  })

  test('a made-up signature opens nothing', async ({ request }) => {
    // The download also takes a signed URL in place of a session -- but only
    // one the server signed, for exactly that path, and not yet expired.
    const forged =
      '/render/deadbeefdeadbeefdeadbeef/download?exp=9999999999&sig=' + 'A'.repeat(43)
    const res = await request.get(forged)
    expect(res.status()).toBe(401)
    expect((await res.json()).detail).toBe('This media link is not valid')
  })
})

test.describe("another user's render", () => {
  test('is not listed, and answers 404 everywhere', async ({
    request,
    token,
  }, testInfo) => {
    // Somebody else: registered here, so the test does not depend on a
    // second fixture account. If registration is closed on this server, the
    // other user cannot be made and the test says so rather than passing.
    const email = `e2e-other-${Date.now()}-${testInfo.workerIndex}@example.com`
    const password = `${CREDENTIALS.password}-other`
    const registered = await request.post('/auth/register', {
      data: { email, password, first_name: 'Other' },
    })
    test.skip(
      ![200, 201].includes(registered.status()),
      `could not register a second user (${registered.status()})`
    )
    const login = await request.post('/auth/jwt/login', {
      form: { username: email, password },
    })
    expect(login.status()).toBe(200)
    const other = `Bearer ${(await login.json()).access_token}`

    const mine = { Authorization: token }
    const theirs = { Authorization: other }
    const created = await request.post('/render', {
      headers: mine,
      data: renderBody([TEMPLATE], { quality: 'draft' }),
    })
    const id = (await created.json()).replace(/"/g, '')

    const listed = await (await request.get('/render', { headers: theirs })).json()
    expect(listed.map(r => r._id)).not.toContain(id)

    const attempts = [
      ['get', `/render/${id}`],
      ['get', `/render/${id}/status`],
      ['get', `/render/${id}/download`],
      ['post', `/render/${id}/deliver`],
      ['post', `/render/rerender/${id}`],
      ['put', `/render/${id}`],
      ['delete', `/render/${id}`],
    ]
    for (const [method, path] of attempts) {
      const res = await request[method](path, {
        headers: theirs,
        ...(method === 'put' ? { data: { name: 'mine now' } } : {}),
      })
      expect(res.status(), `${method.toUpperCase()} ${path}`).toBe(404)
    }

    // Still there, still theirs to whoever made it.
    const status = await request.get(`/render/${id}/status`, { headers: mine })
    expect(status.status()).toBe(200)
  })

  test('there is no way to delete every render at once', async ({
    request,
    token,
  }) => {
    const res = await request.delete('/render', { headers: { Authorization: token } })
    expect(res.status()).toBe(405)
  })
})
