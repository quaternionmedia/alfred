/**
 * `cutRanges`, `followClips` and an excerpt (src/ClipWindow.js) over the
 * fixtures the server's twin reads too (tests/fixtures/, tests/unit/test_cut.py).
 * Plain arithmetic, run in Node: no browser, no server. A fixture both suites
 * pass is a case the two implementations agree on.
 */

const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const { cutRanges, cutSpans, followClips, timelineEnd, toMs } = require('../src/ClipWindow')

const FIXTURES = path.join(__dirname, '..', '..', 'tests', 'fixtures')

const fixtures = folder => {
  const dir = path.join(FIXTURES, folder)
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.json')).sort()
  expect(files.length, `no fixtures under tests/fixtures/${folder}`).toBeGreaterThan(0)
  return files.map(f => [f.replace(/\.json$/, ''), JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'))])
}

/** A span as a timeline of its own: everything outside it, cut (utils/cut.py `excerpt`). */
function excerpt(timeline, start, end) {
  const until = timelineEnd(timeline.clips)
  const [[from, to]] = cutSpans([[start, end]], until)
  const cut = cutRanges(timeline, [[0, from], [to, until]])
  return { clips: cut.clips, duration: toMs(to - from), captions: cut.captions, words: cut.words }
}

test.describe('cutRanges over the shared fixtures', () => {
  for (const [name, fixture] of fixtures('cut')) {
    test(name, () => {
      const given = JSON.parse(JSON.stringify(fixture.given))
      expect(cutRanges(fixture.given, fixture.ranges)).toEqual(fixture.expect)
      // Pure: nothing it is given is changed.
      expect(fixture.given).toEqual(given)
    })
  }
})

test.describe('followClips over the shared fixtures', () => {
  for (const [name, fixture] of fixtures('follow')) {
    test(name, () => {
      const given = JSON.parse(JSON.stringify(fixture.given))
      expect(followClips(fixture.given)).toEqual(fixture.expect)
      expect(fixture.given).toEqual(given)
    })
  }
})

test.describe('an excerpt over the shared fixtures', () => {
  for (const [name, fixture] of fixtures('excerpt')) {
    test(name, () => {
      expect(excerpt(fixture.given, fixture.start, fixture.end)).toEqual(fixture.expect)
    })
  }
})
