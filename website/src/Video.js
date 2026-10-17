import m from 'mithril'
var Stream = require('mithril/stream')

export var Video = {
  clip: null,
  paused: true,
  filename: '',
  // Position within the current clip's source file, in seconds.
  time: Stream(0),
  duration: 0,
  volume: 0.1,
  speed: 1,
}

/** Seconds a clip occupies on the timeline.
 *
 * One rule, shared by playback and by everything sent to the server. The
 * player lays clips end to end by this number and the render request places
 * them by it, so if the two read a clip's length differently -- a string
 * duration, a missing one -- the video that renders is not the one that
 * played.
 */
export const clipSeconds = c => (c ? Number(c.duration) || 0 : 0)

// The shortest piece a cut may leave, in seconds. A cut on a clip's very edge
// would leave a sliver nobody can see or select, and a near-empty layer for
// the renderer.
export const SHORTEST_CUT = 0.1

const toMs = s => Math.round(s * 1000) / 1000

/**
 * Split a clip `at` seconds into it. Returns the two halves, or null when
 * either would be shorter than SHORTEST_CUT.
 *
 * A media clip is a window onto its file, so its halves are two windows that
 * meet: the first ends at `inpoint + at`, and the second starts there and
 * ends where the original did, at `inpoint + duration`. Played or rendered
 * back to back they show exactly what the original showed.
 *
 * A template clip has no in-point to move -- the renderer draws it fresh for
 * its duration -- so its halves are two shorter clips of the same template
 * with the same settings, each drawn from its own start.
 *
 * The halves are copies, settings included, so editing one does not edit the
 * other.
 */
export function splitClip(clip, at) {
  const duration = clipSeconds(clip)
  const cut = toMs(at)
  if (!(cut >= SHORTEST_CUT && duration - cut >= SHORTEST_CUT)) return null

  const copy = () => {
    const { i, ...rest } = JSON.parse(JSON.stringify(clip))
    return rest
  }
  const first = copy()
  const second = copy()
  first.duration = cut
  second.duration = toMs(duration - cut)

  if (clip.type !== 'template') {
    const inpoint = Number(clip.inpoint) || 0
    first.inpoint = inpoint
    first.outpoint = toMs(inpoint + cut)
    second.inpoint = toMs(inpoint + cut)
    second.outpoint = toMs(inpoint + duration)
  }
  return [first, second]
}

export var Edl = {
  edl: [],
  current: 0,
  // Position along the whole timeline, in seconds. A plain number, and read as
  // one everywhere -- three call sites in Preview.js invoked it as `Edl.time()`
  // instead, which threw and took the surrounding handler with it. That is why
  // the arrow keys did nothing and why the spacebar stopped the first time the
  // video reported progress.
  time: 0,

  duration: () => Edl.durations(Edl.edl),

  durations: e => e.reduce((a, c) => a + clipSeconds(c), 0),

  /** Seconds of timeline before clip `i` starts. */
  startOf: i => Edl.durations(Edl.edl.slice(0, i)),

  update: () => {
    let edl = Edl.edl
    Edl.edl = []
    m.redraw.sync()
    Edl.edl = edl
    m.redraw.sync()
  },

  /** Index of the clip covering timeline second `t`.
   *
   * Clamped at both ends. It walked the list with `while (c + edl[i].duration
   * < t)` and no bound, so any `t` at or past the end ran off the array and
   * threw on `undefined.duration` -- which is every press of the `end` button,
   * and the last frame of any playthrough. An empty timeline threw on the
   * first read for the same reason.
   */
  which: t => {
    if (!Edl.edl.length) return 0
    let acc = 0
    for (let i = 0; i < Edl.edl.length; i++) {
      acc += clipSeconds(Edl.edl[i])
      if (t < acc) return i
    }
    return Edl.edl.length - 1
  },

  /** Move the playhead without forcing a redraw.
   *
   * Separate from `jump` because the transport calls this once per animation
   * frame, and `m.redraw.sync()` at 60Hz is a synchronous re-render of the
   * whole editor per frame.
   */
  seek: t => {
    if (!Edl.edl.length) {
      Edl.time = 0
      return
    }
    const clamped = Math.max(0, Math.min(t, Edl.duration()))
    const n = Edl.which(clamped)
    if (n !== Edl.current) {
      Edl.current = n
      Video.clip = Edl.edl[n]
    }
    Edl.time = clamped
    const clip = Edl.edl[n] || {}
    // Within the clip, offset by its in-point: a clip is a window onto a
    // source file, so timeline second 0 of a clip is `inpoint` in the file.
    Video.time(clamped - Edl.startOf(n) + (Number(clip.inpoint) || 0))
  },

  /** Move the playhead and redraw. For handlers, not for the ticker. */
  jump: t => {
    Edl.seek(t)
    m.redraw()
  },

  /**
   * Split the clip under timeline second `t` into two at `t`.
   *
   * Returns the index of the second half, or -1 if `t` was too close to the
   * clip's start or end (or there is nothing on the timeline) -- the caller
   * says so.
   */
  cut: t => {
    if (!Edl.edl.length) return -1
    const n = Edl.which(t)
    const halves = splitClip(Edl.edl[n], t - Edl.startOf(n))
    if (!halves) return -1
    Edl.edl = [...Edl.edl.slice(0, n), ...halves, ...Edl.edl.slice(n + 1)]
    return n + 1
  },
}

export function array_move(arr, old_index, new_index) {
  let element = arr[old_index]
  arr.splice(old_index, 1)
  arr.splice(new_index, 0, element)
  return arr
}
