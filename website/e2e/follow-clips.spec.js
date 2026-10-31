/**
 * `followClips` (src/ClipWindow.js): captions and words follow an edit made
 * with the timeline tools. Plain arithmetic, run in Node: no browser, no server.
 */

const { test, expect } = require('@playwright/test')
const { followClips } = require('../src/ClipWindow')

/** Clips end to end, as the editor lays them: `[key, type, duration, inpoint]`. */
const track = (...clips) => {
  let start = 0
  return clips.map(([key, type, duration, inpoint]) => {
    const clip = { key, type, start, duration, ...(inpoint === undefined ? {} : { inpoint }) }
    start += duration
    return clip
  })
}

// a: 4 s of a.mp4 from 10 s in; b: 4 s of b.mp4 from its start; t: a 2 s title.
const A = ['a', 'video', 4, 10]
const B = ['b', 'video', 4, 0]
const T = ['t', 'template', 2]
const BEFORE = track(A, B, T)

const WORDS = [
  { start: 0.5, end: 1.0, text: 'Hello', segment: 0 },
  { start: 1.2, end: 1.8, text: 'there', segment: 0 },
  // Across the cut from a to b.
  { start: 3.6, end: 4.4, text: 'across', segment: 0 },
  { start: 5.0, end: 5.5, text: 'bee', segment: 1 },
  { start: 7.0, end: 7.5, text: 'end', segment: 1 },
]

const CAPTIONS = [
  { start: 0.5, end: 1.8, text: 'Hello there' },
  { start: 3.6, end: 5.5, text: 'across bee' },
  { start: 7.0, end: 7.5, text: 'end' },
  // No words under these two; the second is past the end of the timeline.
  { start: 8.5, end: 9.5, text: 'Over the title' },
  { start: 11, end: 12, text: 'Past the end' },
]

const follow = after => followClips({ before: BEFORE, after, captions: CAPTIONS, words: WORDS })

/** `[text, start, end]` of each. */
const read = items => items.map(item => [item.text, item.start, item.end])

test.describe('what later material does', () => {
  test('a trim takes the end of a clip and what was said in it, and what follows moves up', () => {
    // Mutation: drop the source-window intersection in keptPieces -- "there" survives, fails.
    const { words, captions } = follow(track(['a', 'video', 1, 10], B, T))
    expect(read(words)).toEqual([
      ['Hello', 0.5, 1],
      // What of it b said.
      ['across', 1, 1.4],
      ['bee', 2, 2.5],
      ['end', 4, 4.5],
    ])
    expect(read(captions)).toEqual([
      // Lost "there": says what is left.
      ['Hello', 0.5, 1],
      ['across bee', 1, 2.5],
      ['end', 4, 4.5],
      ['Over the title', 5.5, 6.5],
      // Past the end: left where it is.
      ['Past the end', 11, 12],
    ])
  })

  test('a longer clip pushes what follows on; what spans the edit stays whole', () => {
    // Mutation: never join runs in `through` -- "across" loses its b half, fails.
    const { words, captions } = follow(track(['a', 'video', 5, 10], B, T))
    expect(read(words)).toEqual([
      ['Hello', 0.5, 1],
      ['there', 1.2, 1.8],
      // From a's 3.6 to b's 0.4, now a second further on: the new material is between.
      ['across', 3.6, 5.4],
      ['bee', 6, 6.5],
      ['end', 8, 8.5],
    ])
    expect(read(captions).slice(0, 2)).toEqual([
      ['Hello there', 0.5, 1.8],
      ['across bee', 3.6, 6.5],
    ])
  })

  test('a moved clip takes its words and captions with it; the rest close up', () => {
    // b to the front.
    // Mutation: keep words in the order given -- fails.
    const { words, captions } = follow(track(B, A, T))
    expect(read(words)).toEqual([
      ['bee', 1, 1.5],
      ['end', 3, 3.5],
      ['Hello', 4.5, 5],
      ['there', 5.2, 5.8],
      // Its halves are apart now; equal, so it keeps the first said.
      ['across', 7.6, 8],
    ])
    expect(read(captions)).toEqual([
      ['Hello there', 4.5, 5.8],
      // Its longer part is b's, which held "bee" and not "across".
      ['bee', 0, 1.5],
      ['end', 3, 3.5],
      ['Over the title', 8.5, 9.5],
      ['Past the end', 11, 12],
    ])
  })

  test('a deleted clip takes its words; a caption with none left goes', () => {
    // Mutation: keep an item no piece holds (`best ? ... : item`) -- "end" stays, fails.
    const { words, captions } = follow(track(A, T))
    expect(read(words)).toEqual([
      ['Hello', 0.5, 1],
      ['there', 1.2, 1.8],
      ['across', 3.6, 4],
    ])
    expect(read(captions)).toEqual([
      ['Hello there', 0.5, 1.8],
      ['across', 3.6, 4],
      ['Over the title', 4.5, 5.5],
      ['Past the end', 11, 12],
    ])
  })

  test('a clip put between two others moves what follows on; one at the end moves nothing', () => {
    const between = follow(track(A, ['new', 'image', 2], B, T))
    expect(read(between.words)).toEqual([
      ['Hello', 0.5, 1],
      ['there', 1.2, 1.8],
      // Its halves are no longer neighbours: it keeps the first.
      ['across', 3.6, 4],
      ['bee', 7, 7.5],
      ['end', 9, 9.5],
    ])
    expect(read(between.captions).slice(0, 2)).toEqual([
      ['Hello there', 0.5, 1.8],
      ['bee', 6, 7.5],
    ])

    const appended = follow([...BEFORE, { key: 'new', type: 'image', start: 10, duration: 2 }])
    appended.words.forEach((word, j) => expect(word).toBe(WORDS[j]))
    appended.captions.forEach((caption, i) => expect(caption).toBe(CAPTIONS[i]))
  })
})

test.describe('the edits that keep the timeline its length', () => {
  test('a slip shows other material in place: its words move, or go out of the window', () => {
    // b from 1 s into its file.
    const { words } = follow(track(A, ['b', 'video', 4, 1], T))
    expect(read(words)).toEqual([
      ['Hello', 0.5, 1],
      ['there', 1.2, 1.8],
      // b's 0 to 0.4 is out of its window.
      ['across', 3.6, 4],
      ['bee', 4, 4.5],
      ['end', 6, 6.5],
    ])
  })

  test('a roll moves the cut and nothing either side of it', () => {
    // a half a second longer, b half a second in.
    const { words, captions } = follow(track(['a', 'video', 4.5, 10], ['b', 'video', 3.5, 0.5], T))
    expect(read(words)).toEqual([
      ['Hello', 0.5, 1],
      ['there', 1.2, 1.8],
      ['across', 3.6, 4],
      ['bee', 5, 5.5],
      ['end', 7, 7.5],
    ])
    // Its parts still follow each other: one caption, where it was, holding both words.
    expect(read(captions).slice(1, 3)).toEqual([
      ['across bee', 3.6, 5.5],
      ['end', 7, 7.5],
    ])
  })

  test('a slide moves the clip and its words between its neighbours', () => {
    // b a second later: a ends a second later, t starts a second into its animation.
    const { words, captions } = follow(track(['a', 'video', 5, 10], B, ['t', 'template', 1, 1]))
    expect(read(words).slice(3)).toEqual([
      ['bee', 6, 6.5],
      ['end', 8, 8.5],
    ])
    // The title lost its first second, and the caption over it with it.
    expect(read(captions).slice(3)).toEqual([
      ['Over the title', 9, 9.5],
      ['Past the end', 11, 12],
    ])
  })
})

test.describe('at the edges', () => {
  test('a moment goes with the clip that starts there, and from the timeline with it', () => {
    // Mutation: test `start <= p.to` for a moment -- it stays with a, fails.
    const words = [{ start: 4, end: 4, text: 'uh', segment: 0 }]
    const after = clips => followClips({ before: BEFORE, after: clips, words }).words
    expect(after(track(B, A))).toEqual([{ start: 0, end: 0, text: 'uh', segment: 0 }])
    expect(after(track(A, T))).toEqual([])
  })

  test('a still loses its end, and a template its animation, as a file does', () => {
    const before = track(['title', 'template', 4], ['still', 'image', 4])
    const said = [
      { start: 1, end: 2, text: 'title' },
      { start: 5, end: 6, text: 'early' },
      { start: 7, end: 7.5, text: 'late' },
    ]
    // The cut between them a second later: the title runs on, the still starts later.
    const after = [
      { key: 'title', type: 'template', start: 0, duration: 5 },
      { key: 'still', type: 'image', start: 5, duration: 3 },
    ]
    expect(read(followClips({ before, after, words: said }).words)).toEqual([
      ['title', 1, 2],
      ['early', 6, 7],
    ])
  })

  test('a caption being typed is left as it is, and nothing it is given is changed', () => {
    const typing = { start: '', end: '2', text: 'half', _key: 3 }
    const given = { before: BEFORE, after: track(B), captions: [typing, ...CAPTIONS], words: WORDS }
    const was = JSON.stringify(given)
    expect(followClips(given).captions[0]).toBe(typing)
    expect(JSON.stringify(given)).toBe(was)
  })

  test('an edit that moved nothing gives back what it was given', () => {
    const after = BEFORE.map(c => ({ ...c }))
    const same = followClips({ before: BEFORE, after, captions: CAPTIONS, words: WORDS })
    same.words.forEach((word, j) => expect(word).toBe(WORDS[j]))
    same.captions.forEach((caption, i) => expect(caption).toBe(CAPTIONS[i]))
  })
})
