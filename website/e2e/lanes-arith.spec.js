/**
 * The lanes' arithmetic (src/lanes/arith.js): ticks, the view, the clips laid
 * out, a sound's envelope over them, and a clip's effects. Plain arithmetic,
 * run in Node: no browser, no server.
 */

const { test, expect } = require('@playwright/test')
const {
  CAPTION_SHORTEST,
  captionEdge,
  cueEnd,
  cueRow,
  dimmed,
  envelope,
  fadesOf,
  inRange,
  inView,
  placed,
  silences,
  tickStep,
  ticks,
  timecode,
  trimCaption,
} = require('../src/lanes/arith')

test.describe('the ruler', () => {
  test('ticks are at least TICK_PX apart, from the steps offered', () => {
    // At 50 px/s, one tick a second is 50 px: too close; two seconds is 100.
    expect(tickStep(50)).toBe(2)
    // At 1 px/s, every two minutes.
    expect(tickStep(1)).toBe(120)
    // Zoomed right in, tenths.
    expect(tickStep(1000)).toBe(0.1)
    // Zoomed right out past every step, the largest.
    expect(tickStep(0.001)).toBe(3600)
    // Mutation: pick the first step at or over the pixels, not the smallest -- fails.
    expect(tickStep(36)).toBe(2)
  })

  test('a label is m:ss, with hours when there are any and tenths under a second', () => {
    expect(timecode(0)).toBe('0:00')
    expect(timecode(65)).toBe('1:05')
    expect(timecode(3661)).toBe('1:01:01')
    expect(timecode(12.8, 0.1)).toBe('0:12.8')
    // Floating point: three tenths is 0.30000000000000004.
    expect(timecode(0.1 * 3, 0.1)).toBe('0:00.3')
    expect(timecode(-4)).toBe('0:00')
  })

  test('ticks run from 0 to the duration, and only those in view', () => {
    expect(ticks(10, 5)).toEqual([
      { at: 0, label: '0:00' },
      { at: 5, label: '0:05' },
      { at: 10, label: '0:10' },
    ])
    expect(ticks(10, 5, 4, 7).map(t => t.at)).toEqual([5])
    expect(ticks(10, 5, 11, 20)).toEqual([])
    // An empty timeline has its 0.
    expect(ticks(0, 1).map(t => t.at)).toEqual([0])
    // Tenths do not accumulate error: the tenth tick is 1, not 0.9999999.
    expect(ticks(1, 0.1).map(t => t.at)).toContain(1)
  })
})

test.describe('the view', () => {
  test('is the box with a screen either side, never before 0', () => {
    expect(inView(0, 1000, 50)).toEqual({ from: 0, to: 40 })
    expect(inView(5000, 1000, 50)).toEqual({ from: 80, to: 140 })
    // No scale yet: a pixel a second.
    expect(inView(10, 10, 0)).toEqual({ from: 0, to: 30 })
  })

  test('a stretch touching the view is in it', () => {
    const view = { from: 10, to: 20 }
    expect(inRange(9, 10, view)).toBe(true)
    expect(inRange(20, 25, view)).toBe(true)
    expect(inRange(0, 9.9, view)).toBe(false)
    expect(inRange(20.1, 30, view)).toBe(false)
  })
})

test.describe('the clips', () => {
  test('are laid end to end by duration, holes skipped, with their in-points', () => {
    const laid = placed([
      { type: 'video', name: 'a', duration: 4, inpoint: 10, outpoint: 14 },
      null,
      { type: 'template', name: 't', duration: 2 },
    ])
    expect(laid.map(at => [at.index, at.start, at.length, at.inpoint])).toEqual([
      [0, 0, 4, 10],
      [2, 4, 2, 0],
    ])
  })
})

test.describe('the envelope', () => {
  const at = { start: 10, length: 2, inpoint: 1 }
  // Two values a second: file seconds 0-0.5 quiet, 0.5-1 louder, 1-1.5 loud, 1.5-2 half, 2-2.5 quiet, 2.5-3 full.
  const peaks = { rate: 2, values: [0.1, 0.2, 1, 0.5, 0.1, 0.9] }

  test('draws the window the clip plays, at the clip place on the timeline', () => {
    // Fine enough to see every value: 100 px/s.
    const points = envelope(at, peaks, 100).split(' ')
    // 2 s at 0.5 s a sample: five samples along the top, five back along the bottom.
    expect(points.length).toBe(10)
    // The first sample is the file's second 1, level 1: the box's top edge.
    expect(points[0]).toBe('10,0')
    // The last along the top is at the clip's end, 12 s, where the file (2.5-3 s) reads 0.9.
    expect(points[4]).toBe('12,0.05')
    // The bottom mirrors the top, in reverse.
    expect(points[9]).toBe('10,1')
  })

  test('zoomed out, one sample a pixel, each the loudest it covers', () => {
    // 1 px/s: a sample a second, covering two values; the loud 1 and the 0.9 must survive.
    const points = envelope(at, peaks, 1).split(' ')
    expect(points.length).toBe(6)
    expect(points[0]).toBe('10,0')
    expect(points[2]).toBe('12,0.05')
  })

  test('past the end of the file, and with nothing to draw, there is silence', () => {
    const beyond = envelope({ start: 0, length: 1, inpoint: 100 }, peaks, 100)
    expect(beyond.split(' ').every(p => p.endsWith(',0.5'))).toBe(true)
    expect(envelope(at, null, 100)).toBe('')
    expect(envelope(at, { rate: 2, values: [] }, 100)).toBe('')
    expect(envelope({ start: 0, length: 0, inpoint: 0 }, peaks, 100)).toBe('')
  })

  test('silences in the file fall inside the window, in timeline seconds', () => {
    const quiet = silences(at, [
      { start: 0, end: 0.5 }, // before the window
      { start: 0.8, end: 1.4 }, // across its start
      { start: 2.9, end: 4 }, // across its end
    ])
    expect(quiet).toEqual([
      { start: 10, end: 10.4 },
      { start: 11.9, end: 12 },
    ])
  })
})

test.describe('the effects', () => {
  test('a fade is drawn only when it was chosen, and never on a template', () => {
    expect(fadesOf({ type: 'video' })).toEqual({ in: 0, out: 0 })
    // otto's default, which old projects carry unchosen, reads as none.
    expect(fadesOf({ type: 'video', fadeIn: 1, fadeOut: 1 })).toEqual({ in: 0, out: 0 })
    expect(fadesOf({ type: 'video', fadeIn: 2, fadeOut: 0.5 })).toEqual({ in: 2, out: 0.5 })
    expect(fadesOf({ type: 'template', fadeIn: 2 })).toEqual({ in: 0, out: 0 })
    expect(fadesOf(null)).toEqual({ in: 0, out: 0 })
  })

  test('an opacity below 1 dims; 1, nothing and nonsense do not', () => {
    expect(dimmed({ opacity: 0.4 })).toBe(0.4)
    expect(dimmed({ opacity: 1 })).toBe(null)
    expect(dimmed({})).toBe(null)
    expect(dimmed({ opacity: 'solid' })).toBe(null)
    expect(dimmed({ opacity: -1 })).toBe(0)
  })
})

test.describe('the cues', () => {
  test('a cue ends at its end, or at its start as a point', () => {
    expect(cueEnd({ start: 4, end: 9 })).toBe(9)
    expect(cueEnd({ start: 4 })).toBe(4)
    expect(cueEnd({ start: 4, end: null })).toBe(4)
  })

  test('chapters sit above, everything else below', () => {
    expect(cueRow({ kind: 'chapter' })).toBe(0)
    expect(cueRow({ kind: 'excerpt' })).toBe(1)
    expect(cueRow({})).toBe(1)
  })
})

test.describe('trimming a caption', () => {
  const caption = { start: 1.5, end: 2.2, text: 'bars.' }

  test('the nearer edge is the one that moves', () => {
    expect(captionEdge(0.2)).toBe('start')
    expect(captionEdge(0.5)).toBe('end')
    expect(captionEdge(0.9)).toBe('end')
  })

  test('an edge follows the pointer, and the other stays', () => {
    expect(trimCaption(caption, 'end', 0.8)).toEqual({ start: 1.5, end: 3 })
    expect(trimCaption(caption, 'start', -1)).toEqual({ start: 0.5, end: 2.2 })
  })

  test('a caption keeps a tenth of a second, and starts no earlier than the timeline', () => {
    expect(CAPTION_SHORTEST).toBe(0.1)
    expect(trimCaption(caption, 'end', -5)).toEqual({ start: 1.5, end: 1.6 })
    expect(trimCaption(caption, 'start', 5)).toEqual({ start: 2.1, end: 2.2 })
    // Mutation: bound the start by the end alone -- fails here.
    expect(trimCaption(caption, 'start', -5)).toEqual({ start: 0, end: 2.2 })
  })

  test('what is not a number moves nothing, and times as typed are read', () => {
    expect(trimCaption({ start: '1.5', end: '2.2' }, 'end', NaN)).toEqual({ start: 1.5, end: 2.2 })
  })
})
