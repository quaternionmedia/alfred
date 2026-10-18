import m from 'mithril'
import { Edl } from './Video'
import { User } from './User'
import { timelineEdl } from './RenderRequest'

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
    // Refused or full: this timeline goes unkept, and the editor carries on.
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

export const Draft = {
  /** The project whose timeline is on screen, once its saved clips are known. */
  project: null,
  /** Its saved timeline, as compared. */
  base: null,
  /** A kept timeline waiting for an answer: `{project, savedAt, clips}`. */
  offer: null,
  /** What was last kept, as compared, so an unchanged timeline is not rewritten. */
  kept: null,
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
  },

  /**
   * `project`'s saved clips have arrived. They are what the timeline is
   * compared with; a kept timeline that differs from them is offered back.
   */
  opened: (project, saved) => {
    Draft.project = project
    Draft.base = shape(saved)
    Draft.kept = null
    const stored = read(project)
    if (!stored || !Array.isArray(stored.clips)) return
    // Kept by someone else in this tab, as far as can be told: not theirs to
    // be offered, and not ours to throw away.
    if (stored.user && User.username && stored.user !== User.username) return
    if (shape(stored.clips) === Draft.base) {
      // Saved since, from here or elsewhere: nothing is unsaved after all.
      forget(project)
      return
    }
    Draft.offer = { project, savedAt: stored.savedAt, clips: stored.clips }
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
    const now = shape(Edl.edl)
    if (now === Draft.kept) return
    Draft.kept = now
    if (now === Draft.base) {
      forget(project)
      return
    }
    write(project, {
      v: 1,
      project,
      user: User.username || null,
      savedAt: Date.now(),
      clips: copies(Edl.edl),
    })
  },

  /** `clips` were saved to `project`: they are its baseline, and nothing kept is unsaved. */
  saved: (project, clips) => {
    if (project !== Draft.project) return
    Draft.base = shape(clips)
    Draft.kept = null
    // Saving what is on screen answers a waiting offer too: it is superseded.
    Draft.offer = null
    forget(project)
    // Anything changed while the save was on its way is unsaved again.
    Draft.observe()
  },

  /** Put the kept timeline back on screen. */
  restore: () => {
    const offer = Draft.offer
    if (!offer) return
    Draft.offer = null
    Edl.edl = copies(offer.clips)
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

/** The offer, where the stages are: on screen whichever stage is open. */
export const DraftOffer = {
  view: () => {
    const offer = Draft.offer
    if (!offer || offer.project !== m.route.param('project')) return null
    const count = offer.clips.length
    const when = offer.savedAt
      ? new Date(offer.savedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : null
    return m('.draftoffer#draft-offer', { role: 'status' }, [
      m('i.material-icons', { 'aria-hidden': 'true' }, 'restore'),
      m(
        'span.draftmessage',
        `This timeline has unsaved changes${when ? ` from ${when}` : ''} — ${count} clip${
          count === 1 ? '' : 's'
        }, kept when the page was left. The saved timeline is showing.`
      ),
      m('button#draft-restore', { type: 'button', onclick: Draft.restore }, 'Restore them'),
      m('button#draft-discard', { type: 'button', onclick: Draft.discard }, 'Discard'),
    ])
  },
}
