import m from 'mithril'
import { error } from 'alertifyjs'
import { Draft } from './Draft'
import { saveTimeline } from './Tools'
import { escapeHtml, requestProblem } from './Problem'

/**
 * The timeline saves itself: a moment after it stops changing, it goes to
 * its project (Tools.saveTimeline), with the captions and words a cut moved.
 * Draft.js keeps the tab's copy until then, for a save that fails or a page
 * left first. docs/journeys.md, "Saving".
 */

// Quiet this long after the last change, then save.
const QUIET_MS = 1000
// After a failed save, try again this long after; then wait for a change.
const RETRY_MS = [5000, 15000, 30000]

export const Autosave = {
  /** The project the state is about. */
  project: null,
  /** 'saved', 'waiting', 'saving' or 'failed'. */
  state: 'saved',
  /** Why the last save failed. */
  why: null,
  timer: null,
  running: null,
  // A change arrived while a save was on its way.
  pending: false,
  tries: 0,
  /** Saves that succeeded since the page loaded. */
  count: 0,

  /** `project`'s timeline changed: differs from what is saved, or is as saved again. */
  follow: (project, differs) => {
    if (project !== Autosave.project) {
      clearTimeout(Autosave.timer)
      Object.assign(Autosave, { project, state: 'saved', why: null, tries: 0 })
    }
    if (!differs) {
      if (!Autosave.running) {
        clearTimeout(Autosave.timer)
        Object.assign(Autosave, { state: 'saved', why: null, tries: 0 })
      }
      return
    }
    Autosave.tries = 0
    if (Autosave.running) {
      Autosave.pending = true
      return
    }
    Autosave.state = 'waiting'
    Autosave.wait(QUIET_MS)
  },

  /** Another project is opening: save this one's now, while its clips are on screen. */
  leave: project => {
    if (project !== Autosave.project || Autosave.state === 'saved') return
    clearTimeout(Autosave.timer)
    saveTimeline(project).then(
      () => Autosave.count++,
      e => error(`Could not save the timeline you left: ${escapeHtml(why(e))}`, 8)
    )
    Object.assign(Autosave, { project: null, state: 'saved', why: null, tries: 0, pending: false })
  },

  wait: ms => {
    clearTimeout(Autosave.timer)
    // The indicator says how it went.
    Autosave.timer = setTimeout(() => Autosave.save().catch(() => {}), ms)
  },

  /** Save now. Resolves once saved; rejects with the reason it was not. */
  save: () => {
    clearTimeout(Autosave.timer)
    Autosave.timer = null
    const project = Autosave.project
    if (!project) return Promise.resolve()
    if (Autosave.running) return Autosave.running.then(Autosave.save)
    Autosave.state = 'saving'
    Autosave.pending = false
    m.redraw()
    Autosave.running = saveTimeline(project)
      .then(() => {
        Autosave.count++
        if (project !== Autosave.project) return
        Autosave.why = null
        Autosave.tries = 0
        Autosave.state = Autosave.pending ? 'waiting' : 'saved'
        if (Autosave.pending) Autosave.wait(QUIET_MS)
      })
      .catch(e => {
        if (project !== Autosave.project) throw e
        Autosave.state = 'failed'
        Autosave.why = why(e)
        // Said once, then on the indicator while it retries.
        if (!Autosave.tries) error(`Could not save the timeline: ${escapeHtml(Autosave.why)}`, 6)
        const next = RETRY_MS[Autosave.tries++]
        if (next) Autosave.wait(next)
        throw e
      })
      .finally(() => {
        Autosave.running = null
        m.redraw()
      })
    return Autosave.running
  },

  /** Saved, or saving now: what a step that reads the saved timeline waits for. */
  settle: () => {
    // A change from the last few hundred milliseconds is noticed now.
    Draft.flush()
    const project = m.route.param('project')
    if (!project || project !== Autosave.project) return Promise.resolve()
    if (Autosave.state === 'saved' && !Autosave.running) return Promise.resolve()
    return Autosave.save()
  },
}

const why = e => requestProblem(e) || 'no answer from the server'

Draft.followers.push(Autosave.follow)
Draft.leavers.push(Autosave.leave)

/** What the indicator says: `{state, icon, text, title}`, or null for nothing to say. */
export function saveState(project, clips) {
  if (!project) {
    return clips
      ? {
          state: 'unsaved',
          icon: 'cloud_off',
          text: 'Not saved',
          title: 'Choose a project on Source to keep this timeline',
        }
      : null
  }
  if (Draft.offer && Draft.offer.project === project) {
    return {
      state: 'held',
      icon: 'pause_circle',
      text: 'Not saved',
      title: 'Restore or discard the changes kept from before (above); then saving goes on',
    }
  }
  // Its saved clips not in yet: nothing to compare with.
  if (Draft.project !== project) return null
  if (project !== Autosave.project || Autosave.state === 'saved') {
    return { state: 'saved', icon: 'cloud_done', text: 'Saved', title: 'The timeline is saved to the project' }
  }
  if (Autosave.state === 'failed') {
    return {
      state: 'failed',
      icon: 'error_outline',
      text: 'Not saved',
      title: `Could not save: ${Autosave.why}. Kept in this tab; it tries again.`,
    }
  }
  return {
    state: Autosave.state,
    icon: 'cloud_upload',
    text: 'Saving…',
    title: 'The timeline saves itself a moment after a change',
  }
}

/** The indicator: saved, saving, or not saved and why, with a retry. */
export const SaveState = {
  view: ({ attrs: { id = 'save-state', clips = 0 } }) => {
    const said = saveState(m.route.param('project'), clips)
    if (!said) return null
    return m(
      `.savestate#${id}`,
      {
        class: said.state,
        'data-state': said.state,
        'data-saves': Autosave.count,
        role: 'status',
        title: said.title,
      },
      [
        m('i.material-icons', { 'aria-hidden': 'true' }, said.icon),
        m('span.savestatetext', said.text),
        said.state === 'failed'
          ? m(
              `button.linklike#${id}-retry`,
              { type: 'button', onclick: () => Autosave.save().catch(() => {}) },
              'Retry'
            )
          : null,
      ]
    )
  },
}

export default Autosave
