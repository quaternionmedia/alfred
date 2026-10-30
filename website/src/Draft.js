import m from 'mithril'
import { Edl } from './Video'
import { User } from './User'
import { timelineEdl } from './RenderRequest'
import { Captions } from './captions/store'
import { Transcript } from './captions/transcript'

/**
 * The unsaved timeline, kept so that leaving the page does not lose it.
 *
 * A timeline lives in the page until it is saved. A reload, a session that
 * ran out -- which sends the page to log in -- or a tab closed by mistake
 * threw away every edit since the last save, with no warning and no way back.
 *
 * So while a project's timeline differs from what is saved, it is kept in
 * sessionStorage, one entry per project, and when the project is opened again
 * in this tab -- after a reload, or after logging in again -- the page offers
 * to bring it back. Saving clears it; so does choosing to discard it. It is
 * this tab's own, like the session it was made in, and goes when the tab
 * does.
 *
 * "Differs" is judged on the timeline as a render would receive it
 * (`timelineEdl`), so the view's bookkeeping and a stored `start` are not
 * changes; and nothing is kept until the project's saved clips are known,
 * since until then there is nothing to differ from.
 *
 * Every touch of storage is guarded: a browser can refuse it outright
 * (private browsing, a full quota, a policy), and losing the draft is better
 * than losing the editor.
 *
 * Captions and words an edit moved with the timeline are kept in the same
 * entry, one write, and come back with it (docs/captions.md, "Drafts").
 */

const PREFIX = 'alfred.draft.'
// At most this often while the timeline changes -- it is drawn on every frame
// while playing -- and once more after the last change.
const EVERY_MS = 400

const key = project => `${PREFIX}${project}`

function store() {
  try {
    return window.sessionStorage
  } catch (e) {
    return null
  }
}

function read(project) {
  try {
    const raw = store().getItem(key(project))
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

function write(project, value) {
  try {
    store().setItem(key(project), JSON.stringify(value))
  } catch (e) {
    // Refused or full: this timeline goes unkept, and an older one with it.
    forget(project)
  }
}

function forget(project) {
  try {
    store().removeItem(key(project))
  } catch (e) {
    // nothing kept to forget
  }
}

/** A timeline as it is compared: placed, as a render would receive it. */
const shape = clips => JSON.stringify(timelineEdl(clips).clips)

/** Clips as they are kept: copies, without the view's index. */
const copies = clips =>
  (clips || []).filter(Boolean).map(clip => {
    const { i, ...rest } = JSON.parse(JSON.stringify(clip))
    return rest
  })

/** A caption as it is kept: no list key. */
const caption = ({ start, end, text }) => ({ start, end, text })

/**
 * The captions and words that moved with `project`'s timeline, unsaved: `{key, captions, words}`,
 * or null. Read from the stores while they hold the project; after, the last read.
 */
function moved(project) {
  if (Transcript.projectId === project && Captions.projectId === project) {
    Draft.moved = Transcript.moved(project)
      ? {
          project,
          key: `${Transcript.version}|${Captions.print()}`,
          captions: Captions.loaded ? Captions.list : null,
          words: Transcript.loaded ? Transcript.words : null,
        }
      : null
  }
  return Draft.moved && Draft.moved.project === project ? Draft.moved : null
}

export const Draft = {
  /** The project whose timeline is on screen, once its saved clips are known. */
  project: null,
  /** Its saved timeline, as compared. */
  base: null,
  /** A kept timeline waiting for an answer: `{project, savedAt, clips}`. */
  offer: null,
  /** What was last kept, as compared, so an unchanged timeline is not rewritten. */
  kept: null,
  /** The captions and words last read as moved (`moved`). */
  moved: null,
  timer: null,
  last: 0,

  /**
   * A project's timeline is about to load. Whatever is on screen now belongs
   * to the one before, and is kept for it first.
   */
  opening: () => {
    Draft.flush()
    Draft.project = null
    Draft.base = null
    Draft.offer = null
    Draft.kept = null
    Draft.moved = null
  },

  /**
   * `project`'s saved clips have arrived. They are what the timeline is
   * compared with; a kept timeline that differs from them is offered back.
   */
  opened: (project, saved) => {
    const stored = read(project)
    // Kept by someone else in this tab, as far as can be told: not theirs to
    // be offered, and not ours to overwrite or throw away -- so this opening
    // keeps nothing for this project at all.
    if (stored && stored.user && User.username && stored.user !== User.username) return
    Draft.project = project
    Draft.base = shape(saved)
    Draft.kept = null
    if (!stored || !Array.isArray(stored.clips)) return
    if (shape(stored.clips) === Draft.base) {
      // Saved since, from here or elsewhere: nothing is unsaved after all.
      forget(project)
      return
    }
    Draft.offer = {
      project,
      savedAt: stored.savedAt,
      clips: stored.clips,
      captions: Array.isArray(stored.captions) ? stored.captions : null,
      words: Array.isArray(stored.words) ? stored.words : null,
    }
    m.redraw()
  },

  /** The timeline was drawn; keep the draft in step with it, soon. */
  observe: () => {
    if (!Draft.project || Draft.offer || Draft.timer) return
    const wait = Math.max(0, EVERY_MS - (Date.now() - Draft.last))
    Draft.timer = setTimeout(Draft.flush, wait)
  },

  /** Keep the timeline now, if it differs from what is saved; forget it if not. */
  flush: () => {
    clearTimeout(Draft.timer)
    Draft.timer = null
    const project = Draft.project
    // Nothing to compare with yet; or a kept timeline is waiting for an
    // answer, and what is on screen is not to overwrite it.
    if (!project || Draft.offer) return
    Draft.last = Date.now()
    const timeline = shape(Edl.edl)
    const extra = moved(project)
    const now = extra ? `${timeline}|${extra.key}` : timeline
    if (now === Draft.kept) return
    Draft.kept = now
    if (!extra && timeline === Draft.base) {
      forget(project)
      return
    }
    write(project, {
      v: 2,
      project,
      user: User.username || null,
      savedAt: Date.now(),
      clips: copies(Edl.edl),
      ...(extra && extra.captions ? { captions: extra.captions.map(caption) } : {}),
      ...(extra && extra.words ? { words: extra.words } : {}),
    })
  },

  /** `clips` were saved to `project`: they are its baseline, and nothing kept is unsaved. */
  saved: (project, clips) => {
    if (project !== Draft.project) return
    Draft.base = shape(clips)
    Draft.kept = null
    Draft.moved = null
    // Saving what is on screen answers a waiting offer too: it is superseded.
    Draft.offer = null
    forget(project)
    // Anything changed while the save was on its way is unsaved again.
    Draft.observe()
  },

  /** The offer can be taken: its captions and words, if any, have somewhere to go. */
  ready: offer =>
    Boolean(offer) && (!(offer.captions || offer.words) || Transcript.settled(offer.project)),

  /** Put the kept timeline back on screen, and the captions and words it moved. */
  restore: () => {
    const offer = Draft.offer
    if (!Draft.ready(offer)) return
    Draft.offer = null
    Edl.edl = copies(offer.clips)
    if (offer.captions || offer.words) Transcript.restore(offer)
    Edl.current = 0
    Edl.time = 0
    // The list changes under Sortable, so it is drawn afresh (see Edl.update).
    Edl.update()
    Draft.flush()
  },

  /** Throw the kept timeline away. */
  discard: () => {
    const offer = Draft.offer
    if (!offer) return
    Draft.offer = null
    forget(offer.project)
    Draft.kept = null
    m.redraw()
  },
}

// Leaving the page -- a reload, a closed tab -- keeps the latest edit, not
// the one before the last throttled write.
if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', () => Draft.flush())
}

// Kept while the stores still hold them, before another project's load.
Captions.leaving.push(() => Draft.flush())
Transcript.leaving.push(() => Draft.flush())

/** The offer, where the stages are: on screen whichever stage is open. */
export const DraftOffer = {
  view: () => {
    const offer = Draft.offer
    if (!offer || offer.project !== m.route.param('project')) return null
    const count = offer.clips.length
    const when = offer.savedAt
      ? new Date(offer.savedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : null
    const ready = Draft.ready(offer)
    const moved =
      offer.captions || offer.words ? ', and the captions and words that moved with them' : ''
    return m('.draftoffer#draft-offer', { role: 'status' }, [
      m('i.material-icons', { 'aria-hidden': 'true' }, 'restore'),
      m(
        'span.draftmessage',
        `This timeline has unsaved changes${when ? ` from ${when}` : ''} — ${count} clip${
          count === 1 ? '' : 's'
        }${moved}, kept when the page was left. The saved timeline is showing.`
      ),
      m(
        'button#draft-restore',
        {
          type: 'button',
          disabled: !ready,
          title: ready ? '' : 'Loading the captions and the words, which come back with it…',
          onclick: Draft.restore,
        },
        'Restore them'
      ),
      m('button#draft-discard', { type: 'button', onclick: Draft.discard }, 'Discard'),
    ])
  },
}
