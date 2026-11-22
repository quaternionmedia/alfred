/**
 * `followClips` (src/ClipWindow.js): captions and words follow an edit made
 * with the timeline tools; and `revealed` and `saidOnto`, what an edit shows
 * that the timeline held no words for, and what was said there put onto it.
 * Plain arithmetic, run in Node: no browser, no server.
 */

const { test, expect } = require('@playwright/test')
const { followClips, revealed, saidOnto } = require('../src/ClipWindow')

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

test.describe('what an edit shows', () => {
  /** A clip of `name` placed at `start`, `duration` long from `inpoint` in its file. */
  const clip = (key, start, duration, inpoint, name = 'a.mp4', type = 'video') => ({
    key,
    name,
    type,
    start,
    duration,
    inpoint,
  })

  test('a longer clip shows its file past where it ended; a shorter one shows nothing', () => {
    const before = [clip('a', 0, 4, 10)]
    expect(revealed(before, [clip('a', 0, 6, 10)])).toEqual([
      { key: 'a', name: 'a.mp4', start: 14, end: 16 },
    ])
    expect(revealed(before, [clip('a', 0, 3, 10)])).toEqual([])
  })

  test('a slip shows what came in at one side; a roll what came in at the start', () => {
    const before = [clip('a', 0, 4, 10)]
    expect(revealed(before, [clip('a', 0, 4, 11.5)])).toEqual([
      { key: 'a', name: 'a.mp4', start: 14, end: 15.5 },
    ])
    expect(revealed(before, [clip('a', 0, 5, 9)])).toEqual([
      { key: 'a', name: 'a.mp4', start: 9, end: 10 },
    ])
  })

  test('a new clip shows all of its window; a template and a picture show no file', () => {
    expect(revealed([], [clip('b', 0, 3, 20, 'b.wav', 'audio')])).toEqual([
      { key: 'b', name: 'b.wav', start: 20, end: 23 },
    ])
    expect(revealed([], [clip('t', 0, 3, 0, 'makeTitle', 'template')])).toEqual([])
    expect(revealed([], [clip('p', 0, 3, 0, 'still.png', 'image')])).toEqual([])
  })

  test('a slip past its whole window shows all of the window it has now', () => {
    expect(revealed([clip('a', 0, 2, 0)], [clip('a', 0, 2, 5)])).toEqual([
      { key: 'a', name: 'a.mp4', start: 5, end: 7 },
    ])
  })

  // What the server answered over 14 to 16 s of a.mp4, in its seconds.
  const STRETCH = {
    start: 14,
    end: 16,
    words: [
      { start: 13.6, end: 14.2, text: 'edge', segment: 7 },
      { start: 14.3, end: 14.7, text: 'three', segment: 7, speaker: 'Ann' },
      { start: 15.1, end: 15.4, text: 'four', segment: 8 },
      { start: 15.8, end: 16.4, text: 'past', segment: 8 },
    ],
    captions: [{ start: 14.3, end: 15.4, text: 'three four' }],
  }

  test('what was said lands where the clip plays it now, its stretches numbered on', () => {
    // The clip at 2 s on the timeline, its file from 10 s: 14 s of the file is at 6 s.
    const added = saidOnto(STRETCH, { start: 2, duration: 6, inpoint: 10 }, {}, 3)
    expect(added.words).toEqual([
      { start: 6.3, end: 6.7, text: 'three', segment: 3, speaker: 'Ann' },
      { start: 7.1, end: 7.4, text: 'four', segment: 4 },
      // Its middle, 16.1 s, is past the stretch; and "edge" is before it.
    ])
    expect(added.captions).toEqual([{ start: 6.3, end: 7.4, text: 'three four' }])
  })

  test('what the clip no longer plays, and what is already held, is not put on', () => {
    // Trimmed back to 15 s of the file since: "four" is past it.
    const shorter = saidOnto(STRETCH, { start: 0, duration: 5, inpoint: 10 }, {}, 0)
    expect(shorter.words.map(w => w.text)).toEqual(['three'])
    // The caption's middle, 14.85 s, is still played; it is cut to the clip.
    expect(shorter.captions).toEqual([{ start: 4.3, end: 5, text: 'three four' }])
    const held = { words: [{ start: 4.3, end: 4.7, text: 'three' }], captions: [] }
    const again = saidOnto(STRETCH, { start: 0, duration: 6, inpoint: 10 }, held, 0)
    expect(again.words.map(w => w.text)).toEqual(['four'])
  })

  test('nothing lands on a clip that no longer plays the stretch', () => {
    expect(saidOnto(STRETCH, { start: 0, duration: 2, inpoint: 0 }, {}, 0)).toEqual({
      words: [],
      captions: [],
    })
  })
})
