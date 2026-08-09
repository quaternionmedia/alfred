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

export var Edl = {
  edl: [],
  current: 0,
  // Position along the whole timeline, in seconds. A plain number, and read as
  // one everywhere -- three call sites in Preview.js invoked it as `Edl.time()`
  // instead, which threw and took the surrounding handler with it. That is why
  // the arrow keys did nothing and why the spacebar stopped the first time the
  // video reported progress.
  time: 0,

  duration: () => Edl.edl.reduce((a, c) => a + (c ? Number(c.duration) || 0 : 0), 0),

  durations: e => e.reduce((a, c) => a + (c ? Number(c.duration) || 0 : 0), 0),

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
      acc += Number(Edl.edl[i].duration) || 0
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
}

export function array_move(arr, old_index, new_index) {
  let element = arr[old_index]
  arr.splice(old_index, 1)
  arr.splice(new_index, 0, element)
  return arr
}
