/**
 * The Audio lane's arithmetic (src/lanes/arith.js `placed`, `silences`) over
 * the fixtures the server's twin reads too (tests/fixtures/sound/,
 * tests/unit/test_sound.py). Plain arithmetic, run in Node.
 */

const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const { placed, silences } = require('../src/lanes/arith')

const FIXTURES = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'sound')

const fixtures = () => {
  const files = fs.readdirSync(FIXTURES).filter(f => f.endsWith('.json')).sort()
  expect(files.length, 'no fixtures under tests/fixtures/sound').toBeGreaterThan(0)
  return files.map(f => [f.replace(/\.json$/, ''), JSON.parse(fs.readFileSync(path.join(FIXTURES, f), 'utf8'))])
}

test.describe('the lane over the shared fixtures', () => {
  for (const [name, fixture] of fixtures()) {
    test(name, () => {
      const at = placed(fixture.given.clips)
      expect(at).toEqual(fixture.expect.placed)
      expect(at.map(a => silences(a, fixture.given.silences))).toEqual(fixture.expect.silences)
    })
  }
})
