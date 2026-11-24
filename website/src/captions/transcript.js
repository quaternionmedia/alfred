import m from 'mithril'
import { auth } from '../Login'
import { requestProblem } from '../Problem'
import { Edl } from '../Video'
import { Player } from '../Player'
import {
  afterCut,
  clipSeconds,
  cutRanges,
  cutSpans,
  followClips,
  inOf,
  timelineEnd,
} from '../ClipWindow'
import { Captions, captionProblem } from './store'

/**
 * The transcript's words, the selection, the cut (`cutRanges`) and its undo; and the
 * words and captions following the timeline tools (`followClips`).
 * Rules: docs/captions.md, "Editing by text".
 */

// How many cuts can be undone.
export const UNDO_DEPTH = 10

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

/** The clips as `followClips` reads them: their times now, each keyed by the clip itself. */
const marked = () => {
  let start = 0
  return Edl.edl.filter(Boolean).map(clip => {
    const duration = clipSeconds(clip)
    const mark = { key: clip, type: clip.type, start, duration, inpoint: inOf(clip) }
    start += duration
    return mark
  })
}

/** Two marks place the same clips the same way. */
const sameMarks = (a, b) =>
  a.length === b.length &&
  a.every(
    (x, n) =>
      x.key === b[n].key &&
      x.start === b[n].start &&
      x.duration === b[n].duration &&
      x.inpoint === b[n].inpoint
  )

/** Copies of the clips, without the view's index. */
const copies = clips =>
  clips.filter(Boolean).map(clip => {
    const { i, ...rest } = JSON.parse(JSON.stringify(clip))
    return rest
  })

/** The timeline as an undo compares it. */
const timelinePrint = () => JSON.stringify(Edl.edl.filter(Boolean).map(({ i, ...clip }) => clip))

export const Transcript = {
  projectId: null,
  words: [],
  loaded: false,
  loading: false,
  error: null,
  // Selected word indexes, inclusive: `{from, to}` or null.
  selection: null,
  // The captions and words moved with the timeline (a cut, an undo, a tool), not yet saved.
  changed: false,
  // What the last cut took, or gave back: `{words, seconds, undone?}`.
  last: null,
  busy: null,
  // Bumped when the words change; paragraphs redraw on it.
  version: 0,
  // Cuts that can be undone, the last one last.
  undos: [],
  // Timeline edits waiting for the words and the captions to arrive.
  pending: [],
  // Called before a project's words are let go, while they are still held.
  leaving: [],

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
      undos: [],
      pending: [],
    })
    Transcript.version++
  },

  /** Load the words of `projectId`, unless they are the ones held. */
  ensure: projectId => {
    if ((projectId || null) === Transcript.projectId) return
    if (Transcript.projectId) Transcript.leaving.forEach(listener => listener(Transcript.projectId))
    if (projectId) Transcript.load(projectId)
    else Transcript.reset()
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
        Transcript.catchUp()
      })
  },

  /** The words and the captions of `projectId` have arrived, or failed to. */
  settled: projectId =>
    Boolean(projectId) &&
    Transcript.projectId === projectId &&
    !Transcript.loading &&
    Captions.projectId === projectId &&
    (Captions.loaded || Boolean(Captions.error)),

  /** The captions and words of `projectId` moved with its timeline and are not saved. */
  moved: projectId =>
    Boolean(projectId) && Transcript.changed && Transcript.projectId === projectId,

  /** The words as a save sends them; undefined when none are held, so the server keeps its own. */
  wordsToSave: () => (Transcript.loaded ? Transcript.words.map(plain) : undefined),

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

  /** The timeline, the captions and the words, as an undo compares them. */
  state: () => ({ timeline: timelinePrint(), captions: Captions.print(), words: Transcript.words }),

  /** The last cut, while nothing else has changed since it; else null. */
  undoable: () => {
    const last = Transcript.undos[Transcript.undos.length - 1]
    if (!last) return null
    const now = Transcript.state()
    const same =
      now.words === last.after.words &&
      now.captions === last.after.captions &&
      now.timeline === last.after.timeline
    return same ? last : null
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
    const undo = {
      clips: copies(Edl.edl),
      captions: Captions.list,
      words: Transcript.words,
      selection: Transcript.selection,
      changed: Transcript.changed,
      at: spans[0][0],
      took: { words: gone, seconds: result.removed },
    }
    Edl.edl = result.clips
    Captions.replace([...result.captions, ...unreadable])
    Captions.sort()
    Transcript.words = result.words
    Transcript.selection = null
    Transcript.changed = true
    Transcript.error = null
    Transcript.last = undo.took
    Transcript.version++
    // Redraw from scratch under Sortable (Edl.update).
    Edl.update()
    undo.after = Transcript.state()
    Transcript.undos = [...Transcript.undos, undo].slice(-UNDO_DEPTH)
    Player.seek(spans[0][0])
    return true
  },

  /** Put back what the last cut took: timeline, captions, words and the selection. Unsaved. */
  undo: () => {
    const undo = Transcript.undoable()
    if (!undo) return false
    Transcript.undos = Transcript.undos.slice(0, -1)
    Edl.edl = copies(undo.clips)
    Captions.replace(undo.captions)
    Captions.sort()
    Transcript.words = undo.words
    Transcript.selection = undo.selection
    Transcript.changed = undo.changed
    Transcript.error = null
    Transcript.last = { ...undo.took, undone: true }
    Transcript.version++
    Edl.update()
    Player.seek(undo.at)
    return true
  },

  /** What the editor holds was saved: nothing is unsaved, and an undo now changes the project. */
  saved: () => {
    Transcript.changed = false
    Transcript.undos.forEach(undo => {
      undo.changed = true
    })
  },

  /** Where the timeline is before an edit with the tools; hand it to `follow` after. */
  mark: () => ({ project: m.route.param('project') || null, clips: marked() }),

  /** An edit with the tools is done: the words and the captions follow the picture. */
  follow: mark => {
    if (!mark || !mark.project) return
    const after = marked()
    if (sameMarks(mark.clips, after)) return
    Transcript.pending.push({ project: mark.project, before: mark.clips, after })
    Transcript.catchUp()
  },

  /** Apply waiting edits once the words and the captions are here. */
  catchUp: () => {
    const project = Transcript.projectId
    Transcript.pending = Transcript.pending.filter(edit => edit.project === project)
    if (!Transcript.pending.length || !Transcript.settled(project)) return
    const edits = Transcript.pending
    Transcript.pending = []
    edits.forEach(edit => Transcript.apply(edit))
    m.redraw()
  },

  /** One edit, through `followClips`. */
  apply: ({ before, after }) => {
    const words = Transcript.loaded ? Transcript.words : []
    const captions = Captions.loaded ? Captions.list : []
    const result = followClips({ before, after, captions, words })
    const moved = (was, now) => was.length !== now.length || now.some((item, n) => item !== was[n])
    const wordsMoved = moved(words, result.words)
    const captionsMoved = moved(captions, result.captions)
    if (wordsMoved) {
      Transcript.words = result.words
      Transcript.selection = null
      Transcript.version++
    }
    if (captionsMoved) {
      Captions.replace(result.captions)
      Captions.sort()
    }
    if (wordsMoved || captionsMoved) Transcript.changed = true
  },

  /** A kept draft's captions and words come back with its timeline (Draft.js). */
  restore: ({ captions, words }) => {
    if (captions) {
      Captions.replace(captions)
      Captions.sort()
    }
    if (words) {
      Transcript.words = words
      Transcript.loaded = true
    }
    Object.assign(Transcript, {
      selection: null,
      last: null,
      error: null,
      undos: [],
      pending: [],
      changed: Boolean(captions || words),
    })
    Transcript.version++
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
}

// A finished transcription brings new words.
Captions.transcribed.push(projectId => {
  if (Transcript.projectId === projectId) Transcript.load(projectId)
})

// Edits made while the captions loaded follow once they are here.
Captions.arrived.push(() => Transcript.catchUp())
