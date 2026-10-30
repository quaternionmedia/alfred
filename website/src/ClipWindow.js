/**
 * A clip's window arithmetic, and `cutRanges` for editing by text.
 * Imports nothing, so its tests run in Node (e2e/cut-ranges.spec.js).
 * Timing.js re-exports it.
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

// ---- cutting time out -------------------------------------------------------

/** Where a placed clip starts on the output: its `start`, absent as 0. */
const startOf = clip => Number(clip && clip.start) || 0

/** Where a timeline of placed clips ends: where the last of them ends. */
export function timelineEnd(clips) {
  return (clips || []).reduce(
    (end, clip) => (clip ? Math.max(end, startOf(clip) + clipSeconds(clip)) : end),
    0
  )
}

/** `ranges` clamped to [0, end], to the ms, empty ones dropped, sorted, overlaps merged. */
export function cutSpans(ranges, end) {
  const spans = []
  for (const range of ranges || []) {
    const [a, b] = Array.isArray(range) ? range : [range && range.start, range && range.end]
    const from = toMs(Math.max(0, Number(a)))
    const to = toMs(Math.min(Number(end) || 0, Number(b)))
    if (!Number.isFinite(from) || !Number.isFinite(to) || toMs(to - from) <= 0) continue
    spans.push([from, to])
  }
  spans.sort((x, y) => x[0] - y[0])
  const merged = []
  for (const [from, to] of spans) {
    const last = merged[merged.length - 1]
    if (last && from <= last[1]) last[1] = Math.max(last[1], to)
    else merged.push([from, to])
  }
  return merged
}

/** How many seconds of `spans` lie before `t`. */
const cutBefore = (t, spans) =>
  spans.reduce((sum, [from, to]) => sum + Math.max(0, Math.min(t, to) - from), 0)

/** Where second `t` lands once `spans` are cut; inside a span, at its start. */
const moved = (t, spans) => toMs(t - cutBefore(t, spans))

/** The stretches of `[from, to)` outside every span. */
function outside(from, to, spans) {
  const parts = []
  let at = from
  for (const [a, b] of spans) {
    if (b <= at) continue
    if (a >= to) break
    if (a > at) parts.push([at, a])
    at = Math.max(at, b)
    if (at >= to) break
  }
  if (at < to) parts.push([at, to])
  return parts.filter(([a, b]) => toMs(b - a) > 0)
}

/** A copy of a clip, settings and all, without the view's index. */
const copy = clip => {
  const { i, ...rest } = JSON.parse(JSON.stringify(clip))
  return rest
}

/** An item's times as numbers, or null while one is not (a caption being typed). */
function timesOf(item) {
  const start = item.start === '' ? NaN : Number(item.start)
  const end = item.end === '' ? NaN : Number(item.end)
  return Number.isFinite(start) && Number.isFinite(end) ? [start, end] : null
}

/** `item` at `[from, to]`: itself when that is where it is. */
const at = (item, from, to) =>
  Number(item.start) === from && Number(item.end) === to ? item : { ...item, start: from, end: to }

/**
 * A caption or word after the cut: moved and trimmed, or null when nothing is left.
 * Zero-length: gone if inside a span, edges included. Non-numeric times: left as is.
 */
export function afterCut(item, spans) {
  const times = timesOf(item)
  if (!times) return item
  const [start, end] = times
  if (end === start && spans.some(([a, b]) => a <= start && start <= b)) return null
  const from = moved(start, spans)
  const to = moved(end, spans)
  if (end > start && toMs(to - from) <= 0) return null
  return at(item, from, to)
}

// ---- a caption's words ------------------------------------------------------

// The longest a caption's text may be (alfred/core/models/captions.py).
const CAPTION_CHARS = 500

const middle = ([start, end]) => (start + end) / 2

/**
 * Captions after an edit, their text rewritten where they lost words.
 * `captions[i]` became `moved[i]`, `words[j]` became `kept[j]`; null is gone.
 * A caption's words: those whose middle lies in it. Lost some: says the rest, by spaces.
 * Lost all: null. Lost none, or held none: as moved. Rules: docs/captions.md, "Editing by text".
 */
export function retext(captions, moved, words, kept) {
  // Words by middle, for a binary search per caption.
  const order = []
  ;(words || []).forEach((word, j) => {
    const times = timesOf(word)
    if (times) order.push([middle(times), j])
  })
  order.sort((x, y) => x[0] - y[0])
  const firstFrom = t => {
    let lo = 0
    let hi = order.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (order[mid][0] < t) lo = mid + 1
      else hi = mid
    }
    return lo
  }
  return (captions || []).map((caption, i) => {
    const after = moved[i]
    const times = timesOf(caption)
    if (!after || !times) return after
    const members = []
    for (let k = firstFrom(times[0]); k < order.length && order[k][0] <= times[1]; k++) {
      members.push(order[k][1])
    }
    if (!members.length) return after
    const span = timesOf(after)
    // Survived, and still under the caption (a move can take a word elsewhere).
    const left = members.filter(j => {
      const word = kept[j] && timesOf(kept[j])
      return word && span && word[0] <= span[1] && word[1] >= span[0]
    })
    if (left.length === members.length) return after
    if (!left.length) return null
    left.sort((a, b) => Number(kept[a].start) - Number(kept[b].start) || a - b)
    const text = left.map(j => String(kept[j].text).trim()).join(' ')
    return { ...after, text: text.slice(0, CAPTION_CHARS).trim() }
  })
}

/**
 * Cut `ranges` ([start, end] pairs, any order) out of `{clips, captions, words}`.
 * Clips are placed by `start`, on any number of tracks. Pure: returns
 * `{clips, captions, words, removed, spans}`. Rules: docs/captions.md, "Editing by text".
 */
export function cutRanges({ clips = [], captions = [], words = [] } = {}, ranges = []) {
  const present = (clips || []).filter(Boolean)
  const spans = cutSpans(ranges, timelineEnd(present))
  const removed = toMs(spans.reduce((sum, [a, b]) => sum + (b - a), 0))
  const kept = []
  for (const clip of present) {
    const start = startOf(clip)
    const length = clipSeconds(clip)
    const end = start + length
    const parts = length > 0 ? outside(start, end, spans) : [[start, start]]
    // Untouched: same clip, moved.
    if (parts.length === 1 && parts[0][0] === start && parts[0][1] === end) {
      kept.push({ ...copy(clip), start: moved(start, spans) })
      continue
    }
    for (const [from, to] of parts) {
      const part = copy(clip)
      place(part, isStill(clip) ? inOf(clip) : inOf(clip) + (from - start), to - from)
      part.start = moved(from, spans)
      // Hard edit at a cut.
      if (from > start) part.fadeIn = 0
      if (to < end) part.fadeOut = 0
      kept.push(part)
    }
  }
  const cut = items => (items || []).map(item => afterCut(item, spans))
  const keptWords = cut(words)
  const keptCaptions = retext(captions, cut(captions), words, keptWords)
  return {
    clips: kept,
    captions: keptCaptions.filter(Boolean),
    words: keptWords.filter(Boolean),
    removed,
    spans,
  }
}
