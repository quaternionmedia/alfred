import m from 'mithril'
import { auth } from '../Login'
import { requestProblem } from '../Problem'
import { cueEnd } from '../lanes/arith'

/**
 * A project's cues, as the Cues lane draws them: moments and stretches of the
 * timeline with a label and a state, written through `PUT /project/{id}/cues`
 * by whatever drives the editor -- qmcp's excerpt flow writes the stretches it
 * proposes and where each stands on its queue. The list is read again now and
 * then while the project is open, sooner while a cue waits on someone, so an
 * answer given elsewhere shows here.
 */

// How long between reads: while something waits, and otherwise.
const SOON_MS = 5000
const LATER_MS = 20000
// States that change without the editor's doing.
const PENDING = new Set(['proposed', 'waiting', 'approved', 'queued', 'rendering'])

export const Cues = {
  projectId: null,
  list: [],
  loaded: false,
  error: null,
  timer: null,

  /** Load the cues of `projectId`, unless they are the ones held. */
  ensure: projectId => {
    if ((projectId || null) === Cues.projectId) return
    if (projectId) Cues.load(projectId)
    else Cues.reset()
  },

  reset: () => {
    Cues.stopPolling()
    Object.assign(Cues, { projectId: null, list: [], loaded: false, error: null })
  },

  load: projectId => {
    Cues.reset()
    Cues.projectId = projectId
    return Cues.read(projectId, false)
  },

  read: (projectId, background) =>
    auth(`/project/${projectId}/cues`, { background })
      .then(answer => {
        if (Cues.projectId !== projectId) return
        Cues.list = (answer && answer.cues) || []
        Cues.loaded = true
        Cues.error = null
      })
      .catch(err => {
        if (Cues.projectId !== projectId) return
        Cues.error = `Could not load the cues: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        if (Cues.projectId !== projectId) return
        Cues.schedule()
        m.redraw()
      }),

  /** Whether any cue is waiting on something that will change it. */
  pending: () => Cues.list.some(cue => PENDING.has(cue.state)),

  schedule: () => {
    Cues.stopPolling()
    const projectId = Cues.projectId
    if (!projectId) return
    Cues.timer = setTimeout(
      () => {
        Cues.timer = null
        if (Cues.projectId === projectId) Cues.read(projectId, true)
      },
      Cues.pending() ? SOON_MS : LATER_MS
    )
  },

  stopPolling: () => {
    clearTimeout(Cues.timer)
    Cues.timer = null
  },

  /** Read the list again now. */
  refresh: () => (Cues.projectId ? Cues.read(Cues.projectId, true) : Promise.resolve()),

  /** The cues under timeline second `t`. */
  at: t => Cues.list.filter(cue => Number(cue.start) <= t && t <= cueEnd(cue)),
}
