/**
 * The timeline tools on the Text lane's captions and words (Lanes.js): what
 * each tool does to the caption or the word pressed, as arithmetic over
 * `{start, end}` items in time order, in timeline seconds. Imports nothing,
 * so its tests run in Node (e2e/lanes-text.spec.js). docs/lanes.md, "Text",
 * says what each tool does.
 *
 * A drag is a gesture, as a clip's is (Timing.js): `textEdit` begins it on
 * the item pressed and `apply(seconds)` gives what the items become for a
 * drag of that many seconds, always from where they began, so nothing
 * accumulates and a drag back to where it started puts them back. The
 * bounds never move an item by themselves: one already past a bound may be
 * brought back inside it, and cannot be pushed further out.
 *
 * A word keeps its place among its neighbours, so the transcript keeps the
 * order it is read in; a caption may pass over another, as the Captions
 * panel lets it.
 */

// The shortest a caption or a word may be made, in seconds.
export const SHORTEST = Object.freeze({ caption: 0.1, word: 0.05 })
// The longest a caption's text may be, as the Captions panel takes it.
export const CAPTION_CHARS = 500

const round = n => Math.round(n * 1000) / 1000
const seconds = value => {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}
const room = (lo, hi) => [Math.min(0, lo), Math.max(0, hi)]
const clamp = (x, [lo, hi]) => Math.max(lo, Math.min(hi, x))
const timesOf = item => ({ start: seconds(item.start), end: seconds(item.end) })

/** Which edge of an item a press `along` it, 0 at its start and 1 at its end, is nearer. */
export const nearerEdge = along => (Number(along) < 0.5 ? 'start' : 'end')

/** A gesture over `range`: `at(moved)` gives the changed items for a drag of `moved`. */
function gesture(range, at) {
  return {
    range,
    apply: moved => {
      const by = clamp(Number(moved) || 0, range)
      return at(by).map(change => ({
        ...change,
        start: round(change.start),
        end: round(change.end),
      }))
    },
  }
}

function trim(kind, items, index, along) {
  const { start, end } = timesOf(items[index])
  const shortest = SHORTEST[kind]
  const before = items[index - 1]
  const after = items[index + 1]
  const bounded = kind === 'word'
  if (nearerEdge(along) === 'start') {
    const lowest = Math.min(start, bounded && before ? Math.max(0, seconds(before.end)) : 0)
    const highest = Math.max(start, end - shortest)
    return gesture(room(lowest - start, highest - start), d => [{ index, start: start + d, end }])
  }
  const lowest = Math.min(end, start + shortest)
  const highest = bounded && after ? Math.max(end, seconds(after.start)) : Infinity
  return gesture(room(lowest - end, highest - end), d => [{ index, start, end: end + d }])
}

function move(kind, items, index) {
  const { start, end } = timesOf(items[index])
  const before = items[index - 1]
  const after = items[index + 1]
  const bounded = kind === 'word'
  const lo = Math.max(-start, bounded && before ? seconds(before.end) - start : -Infinity)
  const hi = bounded && after ? seconds(after.start) - end : Infinity
  return gesture(room(lo, hi), d => [{ index, start: start + d, end: end + d }])
}

function slide(kind, items, index) {
  const { start, end } = timesOf(items[index])
  const shortest = SHORTEST[kind]
  const before = items[index - 1]
  const after = items[index + 1]
  if (!before && !after) {
    return { refusal: `Slide moves a ${kind} between its neighbours, and this one has none.` }
  }
  let lo = -start
  let hi = Infinity
  if (before) {
    const b = timesOf(before)
    lo = Math.max(lo, b.start + shortest - b.end)
  }
  if (after) {
    const a = timesOf(after)
    hi = a.end - shortest - a.start
  }
  return gesture(room(lo, hi), d => {
    const changes = [{ index, start: start + d, end: end + d }]
    if (before) {
      const b = timesOf(before)
      changes.unshift({ index: index - 1, start: b.start, end: b.end + d })
    }
    if (after) {
      const a = timesOf(after)
      changes.push({ index: index + 1, start: a.start + d, end: a.end })
    }
    return changes
  })
}

function roll(kind, items, index, along) {
  const nearest = nearerEdge(along) === 'start' ? index - 1 : index
  const other = nearest === index ? index - 1 : index
  const exists = at => at >= 0 && at + 1 < items.length
  const left = exists(nearest) ? nearest : exists(other) ? other : -1
  if (left < 0) {
    return {
      refusal: `Dual roller moves where two ${kind}s meet, and this one has no neighbour.`,
    }
  }
  const shortest = SHORTEST[kind]
  const a = timesOf(items[left])
  const b = timesOf(items[left + 1])
  return gesture(room(a.start + shortest - a.end, b.end - shortest - b.start), d => [
    { index: left, start: a.start, end: a.end + d },
    { index: left + 1, start: b.start + d, end: b.end },
  ])
}

/** The words said in `[from, to]`, by where each one's middle falls, as one line. */
export function saidIn(words, from, to) {
  return (words || [])
    .filter(w => {
      const middle = (seconds(w.start) + seconds(w.end)) / 2
      return from <= middle && middle <= to
    })
    .map(w => String(w.text || '').trim())
    .filter(Boolean)
    .join(' ')
    .slice(0, CAPTION_CHARS)
    .trim()
}

function slip(kind, items, index, words) {
  if (kind === 'word') return { refusal: 'A word shows only itself: there is nothing to slip.' }
  const spoken = (words || []).filter(w => String(w.text || '').trim())
  if (!spoken.length) {
    return { refusal: 'There is no transcript under the captions to slip this one through.' }
  }
  const item = items[index]
  const { start, end } = timesOf(item)
  const last = Math.max(...spoken.map(w => seconds(w.end)))
  // The caption keeps its place and its length; what moves is the stretch of
  // the transcript it shows. Where nothing is said it keeps the words it had.
  return gesture(room(-start, last - end), d => {
    const said = d === 0 ? '' : saidIn(spoken, start + d, end + d)
    return [{ index, start, end, text: said || item.text }]
  })
}

/**
 * What `tool` does to `items[index]`, pressed `along` it: a gesture whose
 * `apply(seconds)` gives each item it changes as `{index, start, end}`, with
 * `text` for a slip; or `{refusal}`, which says why it cannot act there.
 * `kind` is 'caption' or 'word'; `words` are the transcript's, which a
 * caption's slip reads. Null for a tool that does not drag.
 */
export function textEdit(tool, kind, items, index, along, words = []) {
  if (!items || !items[index]) return null
  switch (tool) {
    case 'trim':
      return trim(kind, items, index, along)
    case 'move':
      return move(kind, items, index)
    case 'slide':
      return slide(kind, items, index)
    case 'dual roller':
      return roll(kind, items, index, along)
    case 'slip':
      return slip(kind, items, index, words)
    default:
      return null
  }
}

/**
 * A caption cut in two at timeline second `at`: `{first, second}`, its text
 * divided where its words are, by how many of the transcript's words under it
 * are said before the cut, or by how far along it the cut is where none are;
 * or `{refusal}`. A word is not cut.
 */
export function textCut(kind, item, at, words = []) {
  if (kind === 'word') return { refusal: 'A word cannot be split.' }
  const { start, end } = timesOf(item)
  const shortest = SHORTEST.caption
  const cut = seconds(at)
  if (!(cut - start >= shortest && end - cut >= shortest)) {
    return { refusal: 'Too close to the start or end of this caption to cut there.' }
  }
  const tokens = String(item.text || '')
    .split(/\s+/)
    .filter(Boolean)
  if (tokens.length < 2) return { refusal: 'A caption of one word cannot be split.' }
  const middles = (words || [])
    .map(w => (seconds(w.start) + seconds(w.end)) / 2)
    .filter(middle => start <= middle && middle <= end)
  const share = middles.length
    ? middles.filter(middle => middle < cut).length / middles.length
    : (cut - start) / (end - start)
  const k = Math.min(tokens.length - 1, Math.max(1, Math.round(share * tokens.length)))
  return {
    first: { ...item, start: round(start), end: round(cut), text: tokens.slice(0, k).join(' ') },
    second: { ...item, start: round(cut), end: round(end), text: tokens.slice(k).join(' ') },
  }
}
