const { request } = require('@playwright/test')
const { CREDENTIALS } = require('./credentials')

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

  await api.dispose()
}
