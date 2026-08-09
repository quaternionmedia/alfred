import m from 'mithril'
import { Video, Edl } from './Video'

/**
 * The transport. What "play" means when the timeline is the subject.
 *
 * It meant nothing before. `Monitor` held a `dom` reference assigned in its
 * own `oncreate`, but `Monitor` was never mounted -- Otto.js imported it and
 * never rendered it -- so `dom` stayed null and every control that reached
 * through it (play, pause, faster, slower, reset speed) threw
 * `Cannot read properties of null` on the first click. The toolbar looked
 * fine and did nothing, which is the worst way for a control to fail.
 *
 * The clock is the timeline, not a file. That distinction matters here more
 * than it would in most editors: `POST /demo/project` builds its timeline out
 * of template clips, so the first project anybody generates is entirely
 * stills. A transport bound to a `<video>` element leaves that project inert,
 * and the first thing a new user tries is the play button.
 *
 * So a ticker advances `Edl.time` in wall-clock seconds scaled by speed, and
 * a video clip's element is slaved to it -- corrected only when it drifts far
 * enough to notice, so ordinary playback keeps its own audio timing rather
 * than being seeked every frame.
 */

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())

// How far the element may drift from the timeline before it is pulled back.
// Small enough that nobody sees a mismatch, large enough that normal decoding
// jitter is not treated as an error and corrected into a stutter.
const DRIFT_TOLERANCE = 0.3

export const Player = {
  /** The live `<video>` for the current clip, or null when a still is shown. */
  dom: null,
  playing: false,
  raf: null,
  last: 0,

  /** Registered by VideoPreview, which is the only thing that owns a video. */
  attach: el => {
    Player.dom = el
    if (el) {
      el.playbackRate = Number(Video.speed) || 1
      el.volume = Video.volume
      if (Player.playing) Player.resume()
    }
  },

  detach: el => {
    if (Player.dom === el) Player.dom = null
  },

  /** Nothing to play is not the same as paused, and reads differently. */
  playable: () => Edl.edl.length > 0,

  toggle: () => (Player.playing ? Player.pause() : Player.play()),

  play: () => {
    if (!Player.playable()) return
    // Starting from the end restarts, rather than sitting still while claiming
    // to play -- which is what a transport that only ever advanced would do
    // after one playthrough.
    if (Edl.time >= Edl.duration() - 0.01) Edl.seek(0)
    Player.playing = true
    Video.paused = false
    Player.resume()
    Player.last = now()
    Player.tick()
    m.redraw()
  },

  pause: () => {
    Player.playing = false
    Video.paused = true
    if (Player.dom) Player.dom.pause()
    if (Player.raf) cancelAnimationFrame(Player.raf)
    Player.raf = null
    m.redraw()
  },

  /** Ask the element to play, tolerating a refusal.
   *
   * `HTMLMediaElement.play()` returns a promise that rejects when the source
   * is not ready or the browser declines to autoplay. Unhandled, that is an
   * uncaught rejection per click; handled, it is simply a frame that has not
   * arrived yet, and the ticker keeps the playhead moving regardless.
   */
  resume: () => {
    if (!Player.dom) return
    const started = Player.dom.play()
    if (started && started.catch) started.catch(() => {})
  },

  seek: t => {
    Edl.seek(t)
    Player.syncElement(true)
    m.redraw()
  },

  speed: rate => {
    Video.speed = rate
    if (Player.dom) Player.dom.playbackRate = Math.max(0.0625, Math.abs(rate) || 1)
    m.redraw()
  },

  faster: () => {
    const s = Number(Video.speed) || 1
    Player.speed(s < 1 ? Number((s + 0.25).toFixed(2)) : Math.min(s * 2, 16))
  },

  slower: () => {
    const s = Number(Video.speed) || 1
    Player.speed(s > 1 ? s / 2 : Math.max(Number((s - 0.25).toFixed(2)), 0.25))
  },

  resetSpeed: () => Player.speed(1),

  /** Keep the video element in step with the timeline playhead. */
  syncElement: force => {
    const el = Player.dom
    if (!el) return
    const clip = Edl.edl[Edl.current]
    if (!clip) return

    const wanted = Edl.time - Edl.startOf(Edl.current) + (Number(clip.inpoint) || 0)
    if (!Number.isFinite(wanted)) return
    if (force || Math.abs(el.currentTime - wanted) > DRIFT_TOLERANCE) {
      // Seeking an element with no source yet throws in some browsers and is
      // meaningless in the rest; the fetch that supplies it will redraw.
      if (el.readyState > 0) el.currentTime = wanted
    }
  },

  tick: () => {
    Player.raf = requestAnimationFrame(() => {
      if (!Player.playing) return

      const t = now()
      const dt = (t - Player.last) / 1000
      Player.last = t

      const next = Edl.time + dt * (Number(Video.speed) || 1)
      const total = Edl.duration()

      if (next >= total) {
        Edl.seek(total)
        Player.pause()
        return
      }

      const wasOn = Edl.current
      Edl.seek(next)
      // Crossing into another clip changes which element is on screen, so the
      // new one is put in the right place rather than left at zero.
      Player.syncElement(Edl.current !== wasOn)
      m.redraw()
      Player.tick()
    })
  },
}

export default Player
