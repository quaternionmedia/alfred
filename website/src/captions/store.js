import m from 'mithril'
import { auth } from '../Login'
import { refusalCode, requestProblem } from '../Problem'

/**
 * A project's captions, as the editor holds them (contract K2).
 *
 * One store for the page: the Captions panel edits it, the viewer's overlay
 * shows the caption under the playhead from it, and a render request takes
 * its captions from it -- so what is drawn into a render is what the editor
 * shows, saved or not, exactly as the timeline itself is sent as it stands.
 *
 * The server is the source on load and after every save; between the two
 * the list here may run ahead of it, and `dirty()` says so.
 */

/**
 * What a project's style says when it says nothing. `enabled` is false: a
 * project's captions are drawn into its renders only once someone has said
 * so, and the server stores it that way.
 */
export const STYLE_DEFAULTS = {
  enabled: false,
  fontsize: null,
  color: null,
  bg: null,
  position: null,
  align: null,
  font: null,
}

// How a style's empty fields are drawn, for the overlay and the controls.
// The server decides what a render draws (alfred/core/utils/captions.py);
// these mirror it.
export const DRAWN = {
  fontsize: 54,
  color: '#ffffff',
  bg: '#000000',
  position: 'bottom',
  align: 'center',
  font: 'DejaVu-Sans',
}

const RUNNING = ['queued', 'transcribing']
const POLL_MS = 1500

let nextKey = 1
const keyed = caption => ({ ...caption, _key: caption._key || nextKey++ })
const plain = ({ _key, ...caption }) => caption
const round = n => Math.round(Number(n) * 1000) / 1000

/** What is wrong with one caption, or '' when nothing is. */
export function captionProblem(c) {
  const start = c.start === '' ? NaN : Number(c.start)
  const end = c.end === '' ? NaN : Number(c.end)
  if (!Number.isFinite(start)) return 'Needs a start time'
  if (start < 0) return 'Starts before the timeline does'
  if (!Number.isFinite(end)) return 'Needs an end time'
  if (end <= start) return 'Ends before it starts'
  if (!String(c.text || '').trim()) return 'Needs some text'
  if (String(c.text).length > 500) return 'Longer than 500 characters'
  return ''
}

/** The format a subtitle file is in, from its name or else its content. */
export function formatOf(name, text) {
  const extension = String(name || '').toLowerCase().split('.').pop()
  if (['srt', 'vtt', 'json'].includes(extension)) return extension
  const head = String(text || '').replace(/^﻿/, '').trimStart()
  if (head.startsWith('WEBVTT')) return 'vtt'
  if (head.startsWith('[') || head.startsWith('{')) return 'json'
  return 'srt'
}

export const Captions = {
  projectId: null,
  list: [],
  style: { ...STYLE_DEFAULTS },
  job: null,
  // A snapshot of what the server holds, to tell an unsaved list from it.
  saved: '',
  loaded: false,
  error: null,
  // What a file held, waiting to be accepted: {name, captions, skipped}.
  review: null,
  // Which request is in flight: 'save', 'import', 'transcribe'.
  busy: null,
  // A transcription asked for while captions exist waits for a yes.
  confirming: false,
  timer: null,

  snapshot: () => JSON.stringify({ list: Captions.list.map(plain), style: Captions.style }),

  dirty: () => Captions.loaded && Captions.snapshot() !== Captions.saved,

  running: () => Boolean(Captions.job && RUNNING.includes(Captions.job.state)),

  /** Take what the server answered as the state. */
  accept: answer => {
    Captions.list = (answer.captions || []).map(keyed)
    Captions.style = { ...STYLE_DEFAULTS, ...(answer.style || {}) }
    Captions.job = answer.job || null
    Captions.saved = Captions.snapshot()
    Captions.loaded = true
  },

  /** Load the captions of `projectId`, unless they are the ones held. */
  ensure: projectId => {
    if (!projectId) {
      if (Captions.projectId) Captions.reset()
      return
    }
    if (projectId !== Captions.projectId) Captions.load(projectId)
  },

  reset: () => {
    Captions.stopPolling()
    Object.assign(Captions, {
      projectId: null,
      list: [],
      style: { ...STYLE_DEFAULTS },
      job: null,
      saved: '',
      loaded: false,
      error: null,
      review: null,
      busy: null,
      confirming: false,
    })
  },

  load: projectId => {
    Captions.reset()
    Captions.projectId = projectId
    return auth(`/project/${projectId}/captions`)
      .then(answer => {
        if (Captions.projectId !== projectId) return
        Captions.accept(answer)
        if (Captions.running()) Captions.poll()
      })
      .catch(err => {
        if (Captions.projectId !== projectId) return
        Captions.error = `Could not load the captions: ${requestProblem(err) || 'no answer'}`
      })
  },

  sort: () => {
    Captions.list = [...Captions.list].sort(
      (a, b) => Number(a.start) - Number(b.start) || Number(a.end) - Number(b.end)
    )
  },

  /** A new caption at `at` seconds, two seconds long, ready for its text. */
  add: at => {
    const start = round(Math.max(0, Number(at) || 0))
    Captions.list = [...Captions.list, keyed({ start, end: round(start + 2), text: '' })]
    Captions.sort()
  },

  remove: key => {
    Captions.list = Captions.list.filter(c => c._key !== key)
  },

  /**
   * Change one field of one caption, exactly as typed.
   *
   * Held as typed, not as a number: mithril writes `value` back on every
   * redraw, and a playing timeline redraws sixty times a second, so a time
   * converted on each keystroke would fight the person typing it ("1." is
   * not a number yet). `commit` settles the list once a field is left.
   */
  update: (key, field, value) => {
    Captions.list = Captions.list.map(c => (c._key === key ? { ...c, [field]: value } : c))
  },

  /** Round what can be read as a time, and put the list back in order. */
  commit: () => {
    Captions.list = Captions.list.map(c => ({
      ...c,
      start: Number.isFinite(Number(c.start)) && c.start !== '' ? round(c.start) : c.start,
      end: Number.isFinite(Number(c.end)) && c.end !== '' ? round(c.end) : c.end,
    }))
    Captions.sort()
  },

  setStyle: patch => {
    Captions.style = { ...Captions.style, ...patch }
  },

  problems: () => Captions.list.map(captionProblem),

  canSave: () =>
    Captions.loaded && !Captions.busy && Captions.problems().every(problem => !problem),

  save: () => {
    const projectId = Captions.projectId
    if (!projectId) return Promise.resolve()
    Captions.commit()
    Captions.busy = 'save'
    Captions.error = null
    const body = {
      captions: Captions.list.map(plain).map(c => ({
        start: Number(c.start),
        end: Number(c.end),
        text: c.text,
      })),
      style: Captions.style,
    }
    return auth(`/project/${projectId}/captions`, { method: 'PUT', body })
      .then(answer => {
        if (Captions.projectId !== projectId) return
        // The job is not the save's to change; keep the one known.
        const job = Captions.job
        Captions.accept(answer)
        Captions.job = answer.job || job
      })
      .catch(err => {
        Captions.error = `Could not save the captions: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        Captions.busy = null
      })
  },

  /** Read a subtitle file through the server, for review. */
  importFile: file => {
    const projectId = Captions.projectId
    if (!projectId || !file) return Promise.resolve()
    Captions.busy = 'import'
    Captions.error = null
    Captions.review = null
    return file
      .text()
      .then(text =>
        auth(`/project/${projectId}/captions/import`, {
          method: 'POST',
          body: { format: formatOf(file.name, text), text },
        })
      )
      .then(answer => {
        if (Captions.projectId !== projectId) return
        Captions.review = {
          name: file.name,
          captions: answer.captions || [],
          skipped: answer.skipped || 0,
        }
      })
      .catch(err => {
        Captions.error = `Could not read ${file.name}: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        Captions.busy = null
      })
  },

  /** Take the reviewed file's captions -- in place of these, or with them -- and save. */
  acceptReview: mode => {
    const review = Captions.review
    if (!review) return Promise.resolve()
    const incoming = review.captions.map(keyed)
    Captions.list = mode === 'append' ? [...Captions.list, ...incoming] : incoming
    Captions.review = null
    return Captions.save()
  },

  dismissReview: () => {
    Captions.review = null
  },

  transcribe: () => {
    const projectId = Captions.projectId
    if (!projectId) return Promise.resolve()
    Captions.confirming = false
    Captions.busy = 'transcribe'
    Captions.error = null
    return auth(`/project/${projectId}/captions/transcribe`, { method: 'POST' })
      .then(answer => {
        if (Captions.projectId !== projectId) return
        Captions.job = answer.job
        Captions.poll()
      })
      .catch(err => {
        Captions.error = `Could not transcribe: ${requestProblem(err) || 'no answer'}`
        // One already under way -- from another tab, or an API client -- makes
        // the same captions: follow it, as if this had started it.
        if (refusalCode(err) === 'transcription_running' && Captions.projectId === projectId) {
          Captions.poll()
        }
      })
      .then(() => {
        Captions.busy = null
      })
  },

  /** Follow a transcription until it settles, then show what it made. */
  poll: () => {
    Captions.stopPolling()
    const projectId = Captions.projectId
    Captions.timer = setTimeout(() => {
      Captions.timer = null
      auth(`/project/${projectId}/captions`, { background: true })
        .then(answer => {
          if (Captions.projectId !== projectId) return
          const job = answer.job || null
          if (job && RUNNING.includes(job.state)) {
            Captions.job = job
            Captions.poll()
            return
          }
          // Settled: done replaced the captions on the server; failed did not.
          if (job && job.state === 'done') Captions.accept(answer)
          else Captions.job = job
        })
        .catch(() => {
          if (Captions.projectId === projectId) Captions.poll()
        })
        .then(() => m.redraw())
    }, POLL_MS)
  },

  stopPolling: () => {
    clearTimeout(Captions.timer)
    Captions.timer = null
  },

  /** The captions at `t` seconds of the timeline. */
  at: t =>
    Captions.list.filter(
      c => !captionProblem(c) && Number(c.start) <= t && t < Number(c.end)
    ),

  /**
   * What a render of `projectId` should carry: the captions and their style
   * when the style draws them -- `enabled: true`, said in so many words --
   * and there are any; else nothing.
   *
   * The editor's own list when it holds this project's, saved or not;
   * otherwise the project's stored ones, which `project` carries.
   */
  forRender: (projectId, project) => {
    const held = projectId && Captions.loaded && Captions.projectId === projectId
    const list = held ? Captions.list : (project && project.captions) || []
    const style = held ? Captions.style : (project && project.caption_style) || STYLE_DEFAULTS
    const usable = list.filter(c => !captionProblem(c)).map(plain)
    if (!usable.length || !style || style.enabled !== true) return {}
    return {
      captions: usable.map(c => ({ start: Number(c.start), end: Number(c.end), text: c.text })),
      caption_style: style,
    }
  },
}
