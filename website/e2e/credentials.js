/**
 * Credentials for the E2E user.
 *
 * Overridable by environment so a shared or long-lived environment does not
 * have to accept a hardcoded account. The defaults match the values the
 * Cypress suite carried in `cypress.json`, so an existing test database keeps
 * working without a re-registration step.
 */
const CREDENTIALS = {
  username: process.env.E2E_EMAIL || 'e@mail.me',
  password: process.env.E2E_PASSWORD || 'sosecur3',
  name: process.env.E2E_NAME || 'alfred',
}

module.exports = { CREDENTIALS }
