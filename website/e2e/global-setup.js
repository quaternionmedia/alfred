const { request } = require('@playwright/test')
const { CREDENTIALS } = require('./credentials')
const { MEDIA_PROJECT } = require('./fixtures')

/**
 * Ensure the E2E user exists before any test runs.
 *
 * The Cypress suite this replaces never did this. Its `loginUI` command typed
 * credentials, clicked submit, and then asserted only that the URL was still
 * `/` -- which is equally true of a failed login. Against a fresh database no
 * such user existed, so every "logged in" test ran logged out and still
 * passed. Registering here, and asserting the login actually took effect in
 * the fixture, is the difference between a suite that checks authenticated
 * behavior and one that only appears to.
 */
module.exports = async () => {
  const baseURL = process.env.E2E_BASE_URL || 'http://localhost:8000'
  const api = await request.newContext({ baseURL })

  const res = await api.post('/auth/register', {
    data: {
      email: CREDENTIALS.username,
      password: CREDENTIALS.password,
      first_name: CREDENTIALS.name,
    },
  })

  // 201 on first run; 400 REGISTER_USER_ALREADY_EXISTS on every run after.
  // Anything else means the API is not in a state the suite can test against,
  // and failing here gives a clearer signal than every spec timing out.
  if (![200, 201, 400].includes(res.status())) {
    throw new Error(
      `E2E setup: could not ensure the test user exists. ` +
        `POST /auth/register returned ${res.status()}: ${await res.text()}`
    )
  }

  // --- shared fixtures, created once ---------------------------------------
  //
  // Specs that need data must not create it themselves. `tools.spec.js` did:
  // it checked for a project by name and created one if absent, which eight
  // parallel workers all did at once, producing three projects called "Tool
  // test" and breaking an unrelated spec that counts rows. Exactly the
  // check-then-create race the /demo/project endpoint had.
  //
  // Global setup runs once, before any worker, so there is nobody to race.
  const token = await login(api)
  await ensureDemoMedia(api, token)
  await ensureMediaProject(api, token)

  await api.dispose()
}

async function login(api) {
  const res = await api.post('/auth/jwt/login', {
    form: { username: CREDENTIALS.username, password: CREDENTIALS.password },
  })
  if (res.status() !== 200) {
    throw new Error(`E2E setup: could not log in (${res.status()})`)
  }
  const body = await res.json()
  return `${body.token_type} ${body.access_token}`
}

/** Synthesise the demo clips locally, so no spec depends on a download. */
async function ensureDemoMedia(api, token) {
  const res = await api.post('/demo/media', { headers: { Authorization: token } })
  if (res.status() !== 200) {
    throw new Error(
      `E2E setup: could not generate demo media (${res.status()}). ` +
        'ffmpeg is required; it is what renders video.'
    )
  }
}

/**
 * One project carrying a real video clip and a template, named MEDIA_PROJECT.
 *
 * Removes duplicates first: earlier runs of the racing helper left several,
 * and a suite that starts from an inconsistent fixture reports failures that
 * have nothing to do with the change under test.
 */
async function ensureMediaProject(api, token) {
  const headers = { Authorization: token }

  const projects = await (await api.get('/project', { headers })).json()
  const existing = projects.filter(p => p.name === MEDIA_PROJECT)
  for (const extra of existing.slice(1)) {
    await api.delete(`/project/${extra._id}`, { headers })
  }
  if (existing.length) return

  const videos = await (await api.get('/videos', { headers })).json()
  const clip = videos.map(String).find(v => v.includes('demo-bars'))
  if (!clip) {
    throw new Error('E2E setup: demo media was generated but is not listed')
  }

  const created = await api.post('/project', {
    headers,
    data: {
      name: MEDIA_PROJECT,
      logic: {},
      fields: [],
      edl: {
        clips: [
          {
            type: 'video',
            name: clip,
            duration: 3.0,
            start: 0.0,
            inpoint: 0.0,
            outpoint: 3.0,
          },
          {
            type: 'template',
            name: 'makeColor',
            duration: 2.0,
            start: 3.0,
            data: { color: '#f2aa4c' },
          },
        ],
        duration: 5.0,
      },
    },
  })
  if (created.status() !== 200) {
    throw new Error(
      `E2E setup: could not create ${MEDIA_PROJECT} (${created.status()})`
    )
  }
}
