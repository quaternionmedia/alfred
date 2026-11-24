/**
 * A clip as a window onto its source.
 *
 * otto plays a clip's source from `inpoint` to `outpoint`, so a clip with an
 * out-point lasts `outpoint - inpoint` seconds whatever its `duration` says,
 * and its place on the output is its `start` (contract C1). The editor lays
 * its single track out end to end by `duration` (`clipSeconds`) and derives
 * every start from the order of the clips. So a clip with a window has to
 * keep `outpoint == inpoint + duration`, or what plays is not what renders.
 *
 * Every change to a clip's length or window goes through this module, which
 * is what keeps that true -- a trim, a cut, a slip, a typed duration. It was
 * kept, or not, by each of those separately: a trim moved a media clip's
 * out-point and left a template's alone, and a typed duration moved neither.
 *
 * What a window is depends on what the source is:
 *
 *   video, audio  a file, played from 0 to its length. Always windowed.
 *   template      drawn on demand from its own second 0, for as long as asked.
 *                 Windowed once it starts anywhere but 0: the second half of a
 *                 cut title continues its animation rather than restarting it.
 *   image         the same picture throughout: no window to move, any length.
 */

import { Library } from './Library'
import { SHORTEST, clipSeconds, inOf, isStill, place, toMs } from './ClipWindow'

// Pure window arithmetic and the text cut live in ClipWindow.js; exported here too.
export {
  SHORTEST,
  clipSeconds,
  cutRanges,
  cutSpans,
  inOf,
  isStill,
  place,
  timelineEnd,
  toMs,
  windowed,
} from './ClipWindow'

const MEDIA = new Set(['video', 'audio'])

/** Make a clip `seconds` long, keeping where it starts in its source. */
export const setLength = (clip, seconds) => place(clip, inOf(clip), Math.max(SHORTEST, seconds))

/**
 * What bounds a clip's window: `end` is the length of its source in seconds
 * -- Infinity when there is no end (a template) or none is known (a file the
 * library could not measure, or a server that measures nothing) -- and a
 * `still` has no position in a source at all.
 */
export function source(clip) {
  if (isStill(clip)) return { still: true, end: Infinity }
  if (clip && MEDIA.has(clip.type)) {
    const known = Library.durationOf(clip.name)
    return { still: false, end: known > 0 ? known : Infinity }
  }
  return { still: false, end: Infinity }
}

// ---- edits ----------------------------------------------------------------
//
// Each edit is a gesture: it begins on some clips, is applied again and again
// as the pointer moves -- always from where the clips were when it began, so
// nothing accumulates -- and is either kept or cancelled. `apply(seconds)`
// takes how far the pointer has moved, in timeline seconds, and returns how
// far the edit actually went once the bounds had their say.
//
// The bounds never move a clip by themselves. A clip already past one -- a
// five-second clip of a three-second file, from before lengths were known --
// may be brought back inside it, but is not pulled there the moment an edit
// begins, and cannot be pushed further out.

const FIELDS = ['inpoint', 'outpoint', 'duration']
const remember = clip => FIELDS.map(key => [key, clip[key]])
const restore = (clip, kept) => {
  for (const [key, value] of kept) {
    if (value === undefined) delete clip[key]
    else clip[key] = value
  }
}
const measure = clip => ({ inpoint: inOf(clip), length: clipSeconds(clip) })
const clamp = (x, [lo, hi]) => Math.max(lo, Math.min(hi, x))
const room = (lo, hi) => [Math.min(0, lo), Math.max(0, hi)]

/** How far a clip's end may move, in seconds: [earlier, later]. */
function endRange(clip) {
  const { inpoint, length } = measure(clip)
  const { end } = source(clip)
  return room(SHORTEST - length, Number.isFinite(end) ? end - inpoint - length : Infinity)
}

/** How far a clip's start may move into its source, keeping its end: [earlier, later]. */
function startRange(clip) {
  const { inpoint, length } = measure(clip)
  // A still has no position in a source to run out of; only its length binds.
  return room(source(clip).still ? -Infinity : -inpoint, length - SHORTEST)
}

/** How far a clip's window may move along its source, keeping its length. */
function slipRange(clip) {
  const { inpoint, length } = measure(clip)
  const { end } = source(clip)
  return room(-inpoint, Number.isFinite(end) ? end - inpoint - length : Infinity)
}

const intersect = ([a, b], [c, d]) => [Math.max(a, c), Math.min(b, d)]

/** A gesture on `clips`, applied by `edit(seconds)` from where they started. */
function gesture(clips, range, edit) {
  const kept = clips.map(remember)
  const reset = () => clips.forEach((clip, n) => restore(clip, kept[n]))
  return {
    range,
    apply: seconds => {
      const moved = clamp(Number(seconds) || 0, range)
      reset()
      edit(moved)
      return moved
    },
    cancel: reset,
  }
}

/**
 * Trim: move the end of `clip`. Longer to the right, shorter to the left; no
 * shorter than SHORTEST, and no further than the end of its source.
 */
export function trim(clip) {
  const { inpoint, length } = measure(clip)
  return gesture([clip], endRange(clip), moved => place(clip, inpoint, length + moved))
}

/**
 * Slip: change which part of its source `clip` shows, keeping its length and
 * its place -- the in-point and out-point move together.
 *
 * The picture follows the pointer, as in other editors: dragging right brings
 * in earlier material (both points move back), dragging left later material.
 * Bounded by the start of the source and, when its length is known, by its
 * end. A template slips through its animation; a still has nothing to slip.
 */
export function slip(clip) {
  if (source(clip).still) {
    return { refusal: 'A still image shows the same picture throughout: there is nothing to slip.' }
  }
  const range = slipRange(clip)
  if (range[0] === 0 && range[1] === 0) {
    return { refusal: 'Nothing to slip: this clip already shows the whole of its file.' }
  }
  const { inpoint, length } = measure(clip)
  // The window moves the other way from the pointer, so the range is turned
  // around for the pointer's distance and back for the window's.
  const pointer = [-range[1], -range[0]]
  return gesture([clip], pointer, moved => place(clip, inpoint - moved, length))
}

/**
 * Move the cut between two adjacent clips: `left` ends `seconds` later and
 * `right` starts `seconds` later in its source, keeping where it ends. What
 * is between them on the timeline is unchanged; the edit point moves.
 */
function moveCut(left, right) {
  const l = measure(left)
  const r = measure(right)
  return gesture(
    [left, right],
    intersect(endRange(left), startRange(right)),
    moved => {
      place(left, l.inpoint, l.length + moved)
      place(right, source(right).still ? r.inpoint : r.inpoint + moved, r.length - moved)
    }
  )
}

/**
 * Dual roller: move the cut between `clips[at]` and `clips[at + 1]`. The
 * first clip's out-point and the second's in-point move together, so the
 * timeline keeps its length and everything after the pair stays put.
 */
export function roll(clips, at) {
  const left = clips[at]
  const right = clips[at + 1]
  if (!left || !right) {
    return { refusal: 'Roll moves the cut between two clips; there is no clip on the other side.' }
  }
  return moveCut(left, right)
}

/**
 * Slide: move `clips[at]` along the timeline without changing what it shows,
 * by changing its neighbours -- the clip before it ends later (its out-point
 * moves) and the clip after it starts later in its source (its in-point
 * moves). The timeline keeps its length. It needs a clip on both sides.
 */
export function slide(clips, at) {
  const before = clips[at - 1]
  const after = clips[at + 1]
  if (!before || !after) {
    const side = !before && !after ? 'on either side' : !before ? 'before it' : 'after it'
    return {
      refusal: `Slide moves a clip between its neighbours, and this one has none ${side}.`,
    }
  }
  return moveCut(before, after)
}

/**
 * Split a clip `at` seconds into it. Returns the two halves, or null when
 * either would be shorter than SHORTEST.
 *
 * The halves are two windows that meet: the first plays from the clip's
 * in-point to the cut, the second from the cut to where the original ended.
 * Played or rendered back to back they show exactly what the original did.
 *
 * That holds for a template as much as a file. A template is drawn for its
 * length, and its animation runs from its own second 0 -- so the second half
 * of a cut title used to start the title over, rather than carry on from
 * where the cut was. It starts at the cut now (otto builds a template long
 * enough to reach its out-point, and plays it from its in-point). A still
 * picture has nowhere to continue from, so its halves are simply shorter.
 *
 * The halves are copies, settings included, so editing one does not edit the
 * other.
 */
export function split(clip, at) {
  const length = clipSeconds(clip)
  const cut = toMs(at)
  if (!(cut >= SHORTEST && length - cut >= SHORTEST)) return null

  const copy = () => {
    const { i, ...rest } = JSON.parse(JSON.stringify(clip))
    return rest
  }
  const first = copy()
  const second = copy()
  const from = inOf(clip)
  place(first, from, cut)
  place(second, isStill(clip) ? from : from + cut, length - cut)
  return [first, second]
}
