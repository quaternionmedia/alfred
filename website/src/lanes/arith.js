/**
 * The lanes' arithmetic (Lanes.js): the ruler's ticks, what is in view, the
 * clips laid end to end, a sound's envelope over the clips that play it, and
 * what of a clip's effects there is to draw. Imports ClipWindow.js and nothing
 * else, so its tests run in Node (e2e/lanes-arith.spec.js).
 */
import { chosenFade, clipSeconds, inOf } from '../ClipWindow'

// The spacings a ruler chooses its ticks from, in seconds.
export const STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600]
// The fewest pixels between two labelled ticks.
export const TICK_PX = 72
// From this many pixels a second a word is drawn with its text: a short word
// said in a third of a second then has room for its letters. Below it, down to
// WORD_MARK_SCALE, a word is a mark, and the captions carry the text; below
// that the Text lane draws the captions alone.
export const WORD_TEXT_SCALE = 120
export const WORD_MARK_SCALE = 8

const MEDIA = new Set(['video', 'audio'])

const positive = (value, fallback) => (Number(value) > 0 ? Number(value) : fallback)
const round = n => Math.round(n * 1000) / 1000

/** The tick spacing at `scale` pixels a second: the smallest step at least `px` apart. */
export function tickStep(scale, px = TICK_PX) {
  const s = positive(scale, 1)
  return STEPS.find(step => step * s >= px) || STEPS[STEPS.length - 1]
}

/**
 * `seconds` as a ruler labels it: `m:ss`, with the hours when there are any,
 * and tenths when `step` is under a second.
 */
export function timecode(seconds, step = 1) {
  const t = Math.max(0, Number(seconds) || 0)
  const tenths = step < 1
  const rounded = tenths ? Math.round(t * 10) / 10 : Math.round(t)
  const whole = Math.floor(rounded)
  const h = Math.floor(whole / 3600)
  const mn = Math.floor((whole % 3600) / 60)
  const s = whole % 60
  const pad = n => String(n).padStart(2, '0')
  const base = h ? `${h}:${pad(mn)}:${pad(s)}` : `${mn}:${pad(s)}`
  return tenths ? `${base}.${Math.round((rounded - whole) * 10)}` : base
}

/**
 * The labelled ticks of a timeline `duration` long, every `step` seconds,
 * those between `from` and `to`: each `{at, label}`.
 */
export function ticks(duration, step, from = 0, to = Infinity) {
  const end = Math.max(0, Number(duration) || 0)
  const last = Math.min(end, to)
  const marks = []
  for (let k = Math.max(0, Math.ceil((from - 1e-9) / step)); k * step <= last + 1e-9; k++) {
    const at = round(k * step)
    marks.push({ at, label: timecode(at, step) })
  }
  return marks
}

/**
 * The seconds a scroll box shows, with a screen's width of margin either
 * side so that a scroll finds what it uncovers already drawn: `{from, to}`.
 */
export function inView(left, width, scale) {
  const s = positive(scale, 1)
  const w = Math.max(0, Number(width) || 0)
  const l = Math.max(0, Number(left) || 0)
  return { from: Math.max(0, (l - w) / s), to: (l + 2 * w) / s }
}

/** Whether the stretch from `start` to `end` touches `view`. */
export const inRange = (start, end, view) => end >= view.from && start <= view.to

/**
 * The clips end to end, as the editor lays them: each `{clip, index, start,
 * length, inpoint}`, `start` on the timeline and `inpoint` in its source.
 */
export function placed(clips) {
  let start = 0
  const out = []
  ;(clips || []).forEach((clip, index) => {
    if (!clip) return
    const length = clipSeconds(clip)
    out.push({ clip, index, start, length, inpoint: inOf(clip) })
    start += length
  })
  return out
}

/** Whether a clip plays a file that can make a sound. */
export const sounding = clip => Boolean(clip) && MEDIA.has(clip.type)

/**
 * A sound's envelope over one placed media clip, as the points of an SVG
 * polygon in a box one unit tall whose x is timeline seconds: `peaks` is the
 * file's `{rate, values}`, each value 0 to 1 at `rate` a second, and the
 * clip's window picks the values it plays. Sampled no finer than a pixel at
 * `scale`, each sample the loudest of the values it covers, so a long file
 * zoomed out draws few points and keeps its peaks. '' when there is nothing
 * to draw.
 */
export function envelope(at, peaks, scale) {
  const rate = positive(peaks && peaks.rate, 0)
  const values = (peaks && Array.isArray(peaks.values) && peaks.values) || []
  if (!rate || !values.length || !(at && at.length > 0)) return ''
  const px = positive(scale, 1)
  const dt = Math.max(1 / rate, 1 / px)
  const n = Math.max(1, Math.ceil(at.length / dt))
  const top = []
  const bottom = []
  for (let i = 0; i <= n; i++) {
    const t = Math.min(at.length, i * dt)
    // The values from this sample to the next; at the clip's end, the last
    // ones it plays, so the envelope closes on what was heard there.
    const b = at.inpoint + Math.min(at.length, t + dt)
    const a = b > at.inpoint + t ? at.inpoint + t : Math.max(at.inpoint, b - dt)
    const from = Math.floor(a * rate)
    const to = Math.max(from + 1, Math.floor(b * rate))
    let level = 0
    for (let k = from; k < to && k < values.length; k++) {
      level = Math.max(level, Number(values[k]) || 0)
    }
    level = Math.min(1, Math.max(0, level))
    const x = round(at.start + t)
    top.push(`${x},${round(0.5 - level / 2)}`)
    bottom.push(`${x},${round(0.5 + level / 2)}`)
  }
  return top.concat(bottom.reverse()).join(' ')
}

/**
 * The file's silences (`[{start, end}]`, in its own seconds) that fall in a
 * placed clip's window, in timeline seconds.
 */
export function silences(at, list) {
  const out = []
  for (const silence of list || []) {
    const from = Math.max(0, Number(silence.start) - at.inpoint)
    const to = Math.min(at.length, Number(silence.end) - at.inpoint)
    if (Number.isFinite(from) && Number.isFinite(to) && to - from > 0) {
      out.push({ start: round(at.start + from), end: round(at.start + to) })
    }
  }
  return out
}

/** A clip's fades as they render, `{in, out}` in seconds: a template adds none at its edges. */
export function fadesOf(clip) {
  if (!clip || clip.type === 'template') return { in: 0, out: 0 }
  return { in: chosenFade(clip.fadeIn), out: chosenFade(clip.fadeOut) }
}

/** A clip's opacity when it is drawn fainter than it is, 0 to 1; null when drawn as it is. */
export function dimmed(clip) {
  const value = clip ? clip.opacity : null
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) && n < 1 ? Math.max(0, n) : null
}

/** Where a cue ends: its end, or its start for a point. */
export const cueEnd = cue =>
  cue.end === null || cue.end === undefined || cue.end === ''
    ? Number(cue.start) || 0
    : Number(cue.end) || 0

/** Which row of the Cues lane a cue sits on: chapters above, everything else below. */
export const cueRow = cue => (cue && cue.kind === 'chapter' ? 0 : 1)
