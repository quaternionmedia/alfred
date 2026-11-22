/**
 * The timeline tools on the Text lane's captions and words
 * (src/lanes/textTools.js). Plain arithmetic, run in Node: no browser, no server.
 */

const { test, expect } = require('@playwright/test')
const { SHORTEST, nearerEdge, saidIn, textCut, textEdit } = require('../src/lanes/textTools')

// Three captions with gaps between them, and the words under them.
const CAPTIONS = [
  { start: 1, end: 2, text: 'Welcome to' },
  { start: 2.5, end: 4, text: 'the show tonight' },
  { start: 6, end: 7, text: 'Good night' },
]
const WORDS = [
  { start: 1.0, end: 1.4, text: 'Welcome' },
  { start: 1.5, end: 1.9, text: 'to' },
  { start: 2.5, end: 2.9, text: 'the' },
  { start: 3.0, end: 3.4, text: 'show' },
  { start: 3.5, end: 3.9, text: 'tonight' },
  { start: 6.0, end: 6.4, text: 'Good' },
  { start: 6.5, end: 6.9, text: 'night' },
]

const drag = (tool, kind, items, index, along, seconds, words = WORDS) =>
  textEdit(tool, kind, items, index, along, words).apply(seconds)

test.describe('trim', () => {
  test('the edge nearer the press follows the drag, and the other stays', () => {
    expect(nearerEdge(0.2)).toBe('start')
    expect(nearerEdge(0.5)).toBe('end')
    expect(drag('trim', 'caption', CAPTIONS, 1, 0.9, 0.5)).toEqual([
      { index: 1, start: 2.5, end: 4.5 },
    ])
    expect(drag('trim', 'caption', CAPTIONS, 1, 0.1, -0.5)).toEqual([
      { index: 1, start: 2, end: 4 },
    ])
  })

  test('a caption keeps a tenth of a second and starts no earlier than the timeline', () => {
    expect(SHORTEST.caption).toBe(0.1)
    expect(drag('trim', 'caption', CAPTIONS, 1, 0.9, -5)).toEqual([
      { index: 1, start: 2.5, end: 2.6 },
    ])
    // Mutation: bound a caption's start by the end alone -- fails here.
    expect(drag('trim', 'caption', CAPTIONS, 0, 0.1, -5)).toEqual([{ index: 0, start: 0, end: 2 }])
  })

  test('a caption may pass over its neighbour; a word stops at its own', () => {
    expect(drag('trim', 'caption', CAPTIONS, 0, 0.9, 1)).toEqual([{ index: 0, start: 1, end: 3 }])
    expect(drag('trim', 'word', WORDS, 0, 0.9, 1)).toEqual([{ index: 0, start: 1, end: 1.5 }])
    expect(drag('trim', 'word', WORDS, 1, 0.1, -1)).toEqual([{ index: 1, start: 1.4, end: 1.9 }])
  })

  test('a bound already passed does not move the item by itself', () => {
    const overlapping = [
      { start: 1, end: 2, text: 'a' },
      { start: 1.8, end: 3, text: 'b' },
    ]
    expect(drag('trim', 'word', overlapping, 1, 0.1, 0)).toEqual([
      { index: 1, start: 1.8, end: 3 },
    ])
    expect(drag('trim', 'word', overlapping, 1, 0.1, -1)).toEqual([
      { index: 1, start: 1.8, end: 3 },
    ])
  })
})

test.describe('move', () => {
  test('a caption moves with its length kept, from the timeline start on', () => {
    expect(drag('move', 'caption', CAPTIONS, 1, 0.5, 1.25)).toEqual([
      { index: 1, start: 3.75, end: 5.25 },
    ])
    expect(drag('move', 'caption', CAPTIONS, 0, 0.5, -3)).toEqual([{ index: 0, start: 0, end: 1 }])
  })

  test('a word moves only as far as its neighbours', () => {
    expect(drag('move', 'word', WORDS, 3, 0.5, 2)).toEqual([{ index: 3, start: 3.1, end: 3.5 }])
    expect(drag('move', 'word', WORDS, 3, 0.5, -2)).toEqual([{ index: 3, start: 2.9, end: 3.3 }])
  })
})

test.describe('slide', () => {
  test('the neighbours near edges move with it, so the gaps stay', () => {
    expect(drag('slide', 'caption', CAPTIONS, 1, 0.5, 0.5)).toEqual([
      { index: 0, start: 1, end: 2.5 },
      { index: 1, start: 3, end: 4.5 },
      { index: 2, start: 6.5, end: 7 },
    ])
  })

  test('each neighbour keeps its shortest length', () => {
    expect(drag('slide', 'caption', CAPTIONS, 1, 0.5, 5)).toEqual([
      { index: 0, start: 1, end: 2.9 },
      { index: 1, start: 3.4, end: 4.9 },
      { index: 2, start: 6.9, end: 7 },
    ])
    expect(drag('slide', 'caption', CAPTIONS, 1, 0.5, -5)).toEqual([
      { index: 0, start: 1, end: 1.1 },
      { index: 1, start: 1.6, end: 3.1 },
      { index: 2, start: 5.1, end: 7 },
    ])
  })

  test('an item with one neighbour slides against it; one with none says so', () => {
    expect(drag('slide', 'caption', CAPTIONS, 0, 0.5, -0.5)).toEqual([
      { index: 0, start: 0.5, end: 1.5 },
      { index: 1, start: 2, end: 4 },
    ])
    expect(textEdit('slide', 'caption', [CAPTIONS[0]], 0, 0.5).refusal).toBe(
      'Slide moves a caption between its neighbours, and this one has none.'
    )
  })
})

test.describe('dual roller', () => {
  test('where it meets the neighbour nearer the press moves, the gap kept', () => {
    // Pressed on its first half: the meeting with the caption before.
    expect(drag('dual roller', 'caption', CAPTIONS, 1, 0.2, 0.4)).toEqual([
      { index: 0, start: 1, end: 2.4 },
      { index: 1, start: 2.9, end: 4 },
    ])
    // On its second half: the meeting with the caption after.
    expect(drag('dual roller', 'caption', CAPTIONS, 1, 0.8, 0.4)).toEqual([
      { index: 1, start: 2.5, end: 4.4 },
      { index: 2, start: 6.4, end: 7 },
    ])
  })

  test('at either end of the list the only meeting moves; alone, it says so', () => {
    expect(drag('dual roller', 'word', WORDS, 0, 0.1, 0.05)).toEqual([
      { index: 0, start: 1, end: 1.45 },
      { index: 1, start: 1.55, end: 1.9 },
    ])
    expect(textEdit('dual roller', 'word', [WORDS[0]], 0, 0.5).refusal).toBe(
      'Dual roller moves where two words meet, and this one has no neighbour.'
    )
  })

  test('both keep their shortest length', () => {
    expect(drag('dual roller', 'word', WORDS, 0, 0.9, 5)).toEqual([
      { index: 0, start: 1, end: 1.75 },
      { index: 1, start: 1.85, end: 1.9 },
    ])
  })
})

test.describe('slip', () => {
  test('a caption keeps its place and shows the words said under it as it moves along', () => {
    expect(drag('slip', 'caption', CAPTIONS, 0, 0.5, 1.5)).toEqual([
      { index: 0, start: 1, end: 2, text: 'the show' },
    ])
    // Dragged back to where it began, it says what it said.
    expect(drag('slip', 'caption', CAPTIONS, 0, 0.5, 0)).toEqual([
      { index: 0, start: 1, end: 2, text: 'Welcome to' },
    ])
  })

  test('where nothing is said it keeps the words it had', () => {
    expect(drag('slip', 'caption', CAPTIONS, 1, 0.5, 1.5)[0].text).toBe('the show tonight')
  })

  test('a word, and a caption with no transcript, say why there is nothing to slip', () => {
    expect(textEdit('slip', 'word', WORDS, 0, 0.5, WORDS).refusal).toBe(
      'A word shows only itself: there is nothing to slip.'
    )
    expect(textEdit('slip', 'caption', CAPTIONS, 0, 0.5, []).refusal).toBe(
      'There is no transcript under the captions to slip this one through.'
    )
  })

  test('what is said is read by where each word is in the middle', () => {
    expect(saidIn(WORDS, 2.6, 3.3)).toBe('the show')
    expect(saidIn(WORDS, 4, 5.9)).toBe('')
  })
})

test.describe('cut', () => {
  test('a caption splits where it is pressed, its text where its words are', () => {
    expect(textCut('caption', CAPTIONS[1], 3.45, WORDS)).toEqual({
      first: { start: 2.5, end: 3.45, text: 'the show' },
      second: { start: 3.45, end: 4, text: 'tonight' },
    })
  })

  test('without words under it, the text divides by how far along the cut is', () => {
    expect(textCut('caption', { start: 0, end: 4, text: 'one two three four' }, 1, [])).toEqual({
      first: { start: 0, end: 1, text: 'one' },
      second: { start: 1, end: 4, text: 'two three four' },
    })
  })

  test('each half keeps a word, whatever the words under it say', () => {
    // Every word is said after the cut, and the first half still has one.
    expect(textCut('caption', CAPTIONS[1], 2.6, WORDS).first.text).toBe('the')
  })

  test('too near an edge, one word, or a word: each says why', () => {
    expect(textCut('caption', CAPTIONS[1], 2.55, WORDS).refusal).toBe(
      'Too close to the start or end of this caption to cut there.'
    )
    expect(textCut('caption', { start: 0, end: 2, text: 'Hello' }, 1, []).refusal).toBe(
      'A caption of one word cannot be split.'
    )
    expect(textCut('word', WORDS[0], 1.2, WORDS).refusal).toBe('A word cannot be split.')
  })
})

test.describe('the tools that do not drag', () => {
  test('time and cut begin no drag', () => {
    expect(textEdit('time', 'caption', CAPTIONS, 0, 0.5)).toBeNull()
    expect(textEdit('cut', 'caption', CAPTIONS, 0, 0.5)).toBeNull()
  })
})
