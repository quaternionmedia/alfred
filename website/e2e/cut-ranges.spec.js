/**
 * `cutRanges` (src/ClipWindow.js), the cut behind editing by text, at its edges.
 * Plain arithmetic, run in Node: no browser, no server.
 */

const { test, expect } = require('@playwright/test')
const { cutRanges, cutSpans } = require('../src/ClipWindow')

/** A clip of a file, placed: `start` on the output, `inpoint` into the file. */
const media = (type, name, start, duration, inpoint = 0) => ({
  type,
  name: `videos/${name}`,
  start,
  duration,
  inpoint,
  outpoint: inpoint + duration,
})

/** What a test reads of each clip: its file, where it starts, and its window. */
const shape = clips =>
  clips.map(c => [c.name, c.start, c.duration, c.inpoint ?? null, c.outpoint ?? null])

/** A single track: three clips end to end, ten seconds in all. */
const TRACK = [
  media('video', 'a.mp4', 0, 4, 10),
  media('video', 'b.mp4', 4, 4, 0),
  { type: 'template', name: 'title', start: 8, duration: 2, data: { text: 'End' } },
]

const CAPTIONS = [
  { start: 0.5, end: 1.5, text: 'Before' },
  { start: 2.5, end: 3.5, text: 'Across the cut' },
  { start: 3.2, end: 4.8, text: 'Inside it' },
  { start: 6.0, end: 7.0, text: 'After' },
]

test.describe('one cut', () => {
  test('a range across a clip boundary splits both clips, and what follows moves up by its length', () => {
    // Mutation: don't shift parts after the cut -- fails.
    const cut = cutRanges({ clips: TRACK, captions: CAPTIONS }, [[3, 5]])
    expect(cut.removed).toBe(2)
    expect(shape(cut.clips)).toEqual([
      ['videos/a.mp4', 0, 3, 10, 13],
      // b.mp4 resumes where the cut ended.
      ['videos/b.mp4', 3, 3, 1, 4],
      ['title', 6, 2, null, null],
    ])
    expect(cut.captions).toEqual([
      { start: 0.5, end: 1.5, text: 'Before' },
      // Overlapped: trimmed.
      { start: 2.5, end: 3, text: 'Across the cut' },
      // "Inside it" is gone.
      { start: 4, end: 5, text: 'After' },
    ])
  })

  test('the parts either side of a cut meet with hard edges, and keep their other fades', () => {
    const clip = { ...media('video', 'a.mp4', 0, 6), fadeIn: 0.5, fadeOut: 0.5 }
    const [first, second] = cutRanges({ clips: [clip] }, [[2, 3]]).clips
    expect([first.fadeIn, first.fadeOut]).toEqual([0.5, 0])
    expect([second.fadeIn, second.fadeOut]).toEqual([0, 0.5])
  })

  test('a template after a cut carries on its animation; a picture keeps its window', () => {
    const clips = [
      { type: 'template', name: 'title', start: 0, duration: 4, data: { text: 'Hi' } },
      { type: 'image', name: 'videos/still.png', start: 4, duration: 4 },
    ]
    const cut = cutRanges({ clips }, [[1, 2], [5, 6]])
    expect(shape(cut.clips)).toEqual([
      ['title', 0, 1, null, null],
      // Animation resumes at 2 s.
      ['title', 1, 2, 2, 4],
      ['videos/still.png', 3, 1, null, null],
      ['videos/still.png', 4, 2, null, null],
    ])
  })

  test('nothing it is given is changed', () => {
    const timeline = { clips: TRACK, captions: CAPTIONS, words: [{ start: 3, end: 3.4, text: 'gone' }] }
    const before = JSON.stringify(timeline)
    cutRanges(timeline, [[3, 5]])
    expect(JSON.stringify(timeline)).toBe(before)
  })
})

test.describe('every track', () => {
  test('several tracks are cut at once, audio-only clips with them', () => {
    // Layered: picture, a title over it, two sounds on their own track.
    const clips = [
      media('video', 'picture.mp4', 0, 10),
      { type: 'template', name: 'title', start: 0, duration: 3, data: { text: 'Over' } },
      media('audio', 'talk.wav', 2, 4),
      media('audio', 'music.wav', 7, 2, 5),
    ]
    const cut = cutRanges({ clips }, [[4, 8]])
    expect(cut.removed).toBe(4)
    expect(shape(cut.clips)).toEqual([
      ['videos/picture.mp4', 0, 4, 0, 4],
      ['videos/picture.mp4', 4, 2, 8, 10],
      ['title', 0, 3, null, null],
      ['videos/talk.wav', 2, 2, 0, 2],
      ['videos/music.wav', 4, 1, 6, 7],
    ])
  })

  test('a clip wholly inside a range goes, on whichever track it is', () => {
    const clips = [media('video', 'picture.mp4', 0, 10), media('audio', 'cough.wav', 5, 1)]
    const cut = cutRanges({ clips }, [[4.5, 6.5]])
    expect(cut.clips.map(c => c.name)).toEqual(['videos/picture.mp4', 'videos/picture.mp4'])
  })
})

test.describe('several ranges', () => {
  test('ranges apart and out of order are cut as one edit', () => {
    // Mutation: drop the sort in cutSpans -- fails.
    const clips = [media('video', 'a.mp4', 0, 10)]
    const captions = [
      { start: 0.5, end: 1.2, text: 'one' },
      { start: 2.0, end: 3.0, text: 'two' },
      { start: 6.5, end: 6.8, text: 'three' },
      { start: 8.0, end: 9.0, text: 'four' },
    ]
    const cut = cutRanges({ clips, captions }, [[6, 7], [1, 2]])
    expect(cut.spans).toEqual([[1, 2], [6, 7]])
    expect(cut.removed).toBe(2)
    expect(shape(cut.clips)).toEqual([
      ['videos/a.mp4', 0, 1, 0, 1],
      ['videos/a.mp4', 1, 4, 2, 6],
      ['videos/a.mp4', 5, 3, 7, 10],
    ])
    expect(cut.captions).toEqual([
      { start: 0.5, end: 1, text: 'one' },
      { start: 1, end: 2, text: 'two' },
      { start: 6, end: 7, text: 'four' },
    ])
  })

  test('ranges that overlap or meet are one range', () => {
    expect(cutSpans([[2, 3], [1, 2.5], [3, 4], [6, 7]], 10)).toEqual([[1, 4], [6, 7]])
    const cut = cutRanges({ clips: [media('video', 'a.mp4', 0, 10)] }, [[2, 3], [1, 2.5], [3, 4]])
    expect(cut.removed).toBe(3)
    expect(shape(cut.clips)).toEqual([
      ['videos/a.mp4', 0, 1, 0, 1],
      ['videos/a.mp4', 1, 6, 4, 10],
    ])
  })
})

test.describe('the edges of the timeline', () => {
  test('a range at the start takes the opening, and everything moves up', () => {
    const cut = cutRanges({ clips: TRACK, captions: CAPTIONS }, [[0, 1]])
    expect(shape(cut.clips)).toEqual([
      ['videos/a.mp4', 0, 3, 11, 14],
      ['videos/b.mp4', 3, 4, 0, 4],
      ['title', 7, 2, null, null],
    ])
    expect(cut.captions[0]).toEqual({ start: 0, end: 0.5, text: 'Before' })
  })

  test('a range at the end takes the ending, and nothing moves', () => {
    const cut = cutRanges({ clips: TRACK, captions: CAPTIONS }, [[9, 10]])
    expect(shape(cut.clips)).toEqual([
      ['videos/a.mp4', 0, 4, 10, 14],
      ['videos/b.mp4', 4, 4, 0, 4],
      ['title', 8, 1, null, null],
    ])
    expect(cut.captions).toEqual(CAPTIONS)
  })

  test('a range past the end cuts nothing, and one over it cuts up to the end', () => {
    // Mutation: no clamp to the end -- fails.
    const past = cutRanges({ clips: TRACK, captions: CAPTIONS }, [[12, 15]])
    expect(past.removed).toBe(0)
    expect(past.clips).toEqual(TRACK)
    const over = cutRanges({ clips: TRACK }, [[9.5, 15]])
    expect(over.removed).toBe(0.5)
    expect(shape(over.clips).at(-1)).toEqual(['title', 8, 1.5, null, null])
  })

  test('an empty or zero-length selection changes nothing', () => {
    for (const ranges of [[], [[3, 3]], [[5, 4]], [[NaN, 2]], undefined]) {
      const cut = cutRanges({ clips: TRACK, captions: CAPTIONS, words: [] }, ranges)
      expect(cut.removed, JSON.stringify(ranges)).toBe(0)
      expect(cut.clips).toEqual(TRACK)
      expect(cut.captions).toEqual(CAPTIONS)
    }
  })

  test('an empty timeline has nothing to cut', () => {
    const cut = cutRanges({ clips: [], words: [{ start: 1, end: 2, text: 'kept' }] }, [[0, 5]])
    expect(cut).toMatchObject({ clips: [], removed: 0, words: [{ start: 1, end: 2, text: 'kept' }] })
  })
})

test.describe('the words', () => {
  // "and"/"then" overlap; "uh" takes no time.
  const WORDS = [
    { start: 1.0, end: 1.4, text: 'So', segment: 0 },
    { start: 1.4, end: 1.9, text: 'and', segment: 0 },
    { start: 1.8, end: 2.2, text: 'then', segment: 0 },
    { start: 2.5, end: 2.5, text: 'uh', segment: 0 },
    { start: 3.0, end: 3.5, text: 'done.', segment: 1 },
  ]
  const clips = [media('audio', 'talk.wav', 0, 5)]

  test('the words cut go, later words shift, and one the cut only overlaps is trimmed', () => {
    // "then" + "uh": 1.8 to 2.5.
    const cut = cutRanges({ clips, words: WORDS }, [[1.8, 2.5]])
    expect(cut.removed).toBe(0.7)
    expect(cut.words).toEqual([
      { start: 1.0, end: 1.4, text: 'So', segment: 0 },
      // "and" overlapped "then": trimmed.
      { start: 1.4, end: 1.8, text: 'and', segment: 0 },
      { start: 2.3, end: 2.8, text: 'done.', segment: 1 },
    ])
  })

  test('a word that takes no time goes when a range holds it, and moves when not', () => {
    // Mutation: half-open range test -- "uh" survives, fails.
    expect(cutRanges({ clips, words: WORDS }, [[2.2, 2.5]]).words.map(w => w.text)).toEqual([
      'So',
      'and',
      'then',
      'done.',
    ])
    const later = cutRanges({ clips, words: WORDS }, [[1, 1.4]]).words
    expect(later.find(w => w.text === 'uh')).toEqual({ start: 2.1, end: 2.1, text: 'uh', segment: 0 })
  })

  test('a caption being typed, its times not yet numbers, is left as it is', () => {
    const typing = { start: '', end: '2', text: 'half', _key: 7 }
    expect(cutRanges({ clips, captions: [typing] }, [[0, 1]]).captions).toEqual([typing])
  })
})
