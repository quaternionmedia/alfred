import m from 'mithril'
import { auth } from '../Login'
import { requestProblem } from '../Problem'
import { Edl } from '../Video'
import { Player } from '../Player'
import { saveTimeline } from '../Tools'
import { afterCut, cutRanges, cutSpans, timelineEnd } from '../ClipWindow'
import { Captions, captionProblem } from './store'

/**
 * The transcript's words, the selection, and the cut (`cutRanges`).
 * No undo. Rules and timing: docs/captions.md, "Editing by text".
 */

/** A word as the server keeps it. */
const plain = ({ start, end, text, segment }) => ({
  start,
  end,
  text,
  ...(segment === undefined || segment === null ? {} : { segment }),
})

/** The editor's clips, each placed where the editor plays it. */
const placed = () =>
  Edl.edl.filter(Boolean).map((clip, i) => ({ ...clip, start: Edl.startOf(i) }))

export const Transcript = {
  projectId: null,
  words: [],
  loaded: false,
  loading: false,
  error: null,
  // Selected word indexes, inclusive: `{from, to}` or null.
  selection: null,
  // A cut not yet saved.
  changed: false,
  // What the last cut took: `{words, seconds}`.
  last: null,
  busy: null,
  // Bumped when the words change; paragraphs redraw on it.
  version: 0,

  reset: () => {
    Object.assign(Transcript, {
      projectId: null,
      words: [],
      loaded: false,
      loading: false,
      error: null,
      selection: null,
      changed: false,
      last: null,
      busy: null,
    })
    Transcript.version++
  },

  /** Load the words of `projectId`, unless they are the ones held. */
  ensure: projectId => {
    if (!projectId) {
      if (Transcript.projectId) Transcript.reset()
      return
    }
    if (projectId !== Transcript.projectId) Transcript.load(projectId)
  },

  load: projectId => {
    Transcript.reset()
    Transcript.projectId = projectId
    Transcript.loading = true
    return auth(`/project/${projectId}/captions/words`)
      .then(answer => {
        if (Transcript.projectId !== projectId) return
        Transcript.words = answer.words || []
        Transcript.loaded = true
      })
      .catch(err => {
        if (Transcript.projectId !== projectId) return
        Transcript.error = `Could not load the transcript: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        if (Transcript.projectId !== projectId) return
        Transcript.loading = false
        Transcript.version++
      })
  },

  select: (from, to) => {
    const last = Transcript.words.length - 1
    if (from === null || from === undefined || last < 0) {
      Transcript.selection = null
      return
    }
    const a = Math.max(0, Math.min(from, to, last))
    const b = Math.min(last, Math.max(from, to))
    Transcript.selection = { from: a, to: b }
  },

  clear: () => {
    Transcript.selection = null
  },

  /** `[first.start, last.end]` of the selection, or null. */
  span: () => {
    const selected = Transcript.selection
    if (!selected) return null
    const first = Transcript.words[selected.from]
    const last = Transcript.words[selected.to]
    if (!first || !last) return null
    return [Number(first.start), Number(last.end)]
  },

  /** The selection's span as cut: clamped to the timeline; [] if empty. */
  spans: () => {
    const span = Transcript.span()
    return span ? cutSpans([span], timelineEnd(placed())) : []
  },

  /** Indexes of the words a cut would remove. */
  going: () => {
    const spans = Transcript.spans()
    const going = new Set()
    if (!spans.length) return going
    Transcript.words.forEach((word, i) => {
      if (afterCut(word, spans) === null) going.add(i)
    })
    return going
  },

  /** This project's captions are loaded (a cut moves them). */
  captionsHeld: () => Captions.loaded && Captions.projectId === Transcript.projectId,

  /** Why the selection cannot be cut, or '' when it can. */
  cannotCut: () => {
    if (!Transcript.selection) return 'Select the words to cut first.'
    // Without them, saving would write no captions.
    if (!Transcript.captionsHeld()) return 'Loading the captions, which the cut moves too…'
    if (!Transcript.spans().length) {
      return 'Those words take no time on the timeline, so there is nothing to cut.'
    }
    return ''
  },

  /** Cut the selection from timeline, captions and words; playhead to the cut. Unsaved. */
  cut: () => {
    if (Transcript.cannotCut()) return false
    const spans = Transcript.spans()
    // Captions still being typed are left as they are.
    const [readable, unreadable] = Captions.list.reduce(
      ([ok, not], c) => (captionProblem(c) ? [ok, [...not, c]] : [[...ok, c], not]),
      [[], []]
    )
    const result = cutRanges({ clips: placed(), captions: readable, words: Transcript.words }, spans)
    const gone = Transcript.words.length - result.words.length
    Edl.edl = result.clips
    Captions.replace([...result.captions, ...unreadable])
    Captions.sort()
    Transcript.words = result.words
    Transcript.selection = null
    Transcript.changed = true
    Transcript.error = null
    Transcript.last = { words: gone, seconds: result.removed }
    Transcript.version++
    // Redraw from scratch under Sortable (Edl.update).
    Edl.update()
    Player.seek(spans[0][0])
    return true
  },

  /** The word under timeline second `t`, by index; -1 for none. */
  at: t => {
    const words = Transcript.words
    // Binary search: words are in start order.
    let lo = 0
    let hi = words.length - 1
    let found = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (Number(words[mid].start) <= t) {
        found = mid
        lo = mid + 1
      } else hi = mid - 1
    }
    if (found < 0) return -1
    const word = words[found]
    return t < Number(word.end) ? found : -1
  },

  /** Save the timeline, then captions and words together. Resolves to success. */
  save: () => {
    const projectId = Transcript.projectId
    if (!projectId || Transcript.busy || !Transcript.captionsHeld()) return Promise.resolve(false)
    Transcript.busy = 'save'
    Transcript.error = null
    return saveTimeline(projectId)
      .then(
        () => Captions.save({ words: Transcript.words.map(plain) }),
        err => {
          Transcript.error = `Could not save the timeline: ${requestProblem(err) || 'no answer'}`
          return null
        }
      )
      .then(saved => {
        if (saved === false) {
          Transcript.error = `The timeline is saved, but not the captions and the words: ${
            Captions.error || 'no answer'
          }`
        }
        if (saved === true && Transcript.projectId === projectId) Transcript.changed = false
        Transcript.busy = null
        m.redraw()
        return saved === true
      })
  },
}

// A finished transcription brings new words.
Captions.transcribed.push(projectId => {
  if (Transcript.projectId === projectId) Transcript.load(projectId)
})
