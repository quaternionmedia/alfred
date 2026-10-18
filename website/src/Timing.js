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

// The shortest a clip may be made, in seconds. A trim, a cut or a roll that
// would leave less leaves this much: a sliver nobody can see or select is a
// near-empty layer for the renderer.
export const SHORTEST = 0.1

/** Seconds, to the millisecond: what is stored, so sums do not drift. */
export const toMs = s => Math.round(s * 1000) / 1000

/** Seconds a clip occupies on the timeline. One rule, shared by playback and
 * by everything sent to the server (see Video.js). */
export const clipSeconds = c => (c ? Number(c.duration) || 0 : 0)

/** Where in its source a clip starts playing, in seconds. */
export const inOf = clip => (clip ? Number(clip.inpoint) || 0 : 0)

const MEDIA = new Set(['video', 'audio'])

/** A still picture: a length, but no position in a source to move. */
export const isStill = clip => Boolean(clip) && clip.type === 'image'

/** Whether a clip carries a window that its length has to be kept in step with. */
export function windowed(clip) {
  if (!clip) return false
  return MEDIA.has(clip.type) || clip.inpoint != null || clip.outpoint != null
}

/**
 * Give a clip its window: start `inpoint` seconds into its source, and play
 * for `length` seconds.
 *
 * Writes `duration`, and -- for a clip that has a window, or is given one by
 * starting past 0 -- `inpoint` and `outpoint` with them, so the three always
 * agree. A template starting at 0 with no window keeps none: it is the same
 * clip either way, and an unchanged clip should not change shape.
 */
export function place(clip, inpoint, length) {
  const seconds = toMs(Math.max(0, length))
  clip.duration = seconds
  const still = isStill(clip)
  const from = toMs(Math.max(0, inpoint))
  if (!windowed(clip) && (still || from === 0)) return clip
  // A picture's in-point means nothing; one it already carries is kept as it
  // is, and only the out-point follows the length.
  const start = still ? inOf(clip) : from
  clip.inpoint = start
  clip.outpoint = toMs(start + seconds)
  return clip
}

/** Make a clip `seconds` long, keeping where it starts in its source. */
export const setLength = (clip, seconds) => place(clip, inOf(clip), Math.max(SHORTEST, seconds))

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
