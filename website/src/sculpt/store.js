import m from 'mithril'
import { auth } from '../Login'
import { requestProblem } from '../Problem'
import { Flow } from '../Stages'
import { Cues } from '../cues/store'
import { Transcript } from '../captions/transcript'

/**
 * The Sculpt stage's state: the recipes on offer (`GET /recipes`), which are
 * chosen and with what values, the open project's drafts and the run that
 * makes them (`GET`, `POST` and `DELETE /project/{id}/drafts`). Rules:
 * docs/drafts.md.
 *
 * A run is the worker's, so the job is read again every couple of seconds
 * while it is queued or running; when it is done the project list and the
 * cues are read again, since both changed.
 */

const RUNNING = ['queued', 'running']
const POLL_MS = 2000

export const Sculpt = {
  recipes: [],
  recipesLoaded: false,
  recipesError: null,
  // The recipes ticked, by id, and the values typed for each recipe's fields.
  chosen: new Set(),
  values: {},

  projectId: null,
  job: null,
  drafts: [],
  loaded: false,
  error: null,
  // Which request is in flight: 'run' or 'drop'.
  busy: null,
  timer: null,
  // The drafts ticked to drop, by id.
  marked: new Set(),

  /** The recipes, asked for once; `force` asks again. */
  loadRecipes: opts => {
    if (Sculpt.recipesLoaded && !(opts && opts.force)) return
    Sculpt.recipesLoaded = true
    auth('/recipes')
      .then(recipes => {
        Sculpt.recipes = recipes || []
        Sculpt.recipesError = null
        if (!Sculpt.chosen.size && Sculpt.recipes.length) Sculpt.chosen.add(Sculpt.recipes[0].id)
      })
      .catch(err => {
        Sculpt.recipesLoaded = false
        Sculpt.recipesError = `Could not load the recipes: ${requestProblem(err) || 'no answer'}`
      })
  },

  /** Load the drafts of `projectId`, unless they are the ones held. */
  ensure: projectId => {
    if ((projectId || null) === Sculpt.projectId) return
    if (projectId) Sculpt.load(projectId)
    else Sculpt.reset()
  },

  reset: () => {
    Sculpt.stopPolling()
    Object.assign(Sculpt, {
      projectId: null,
      job: null,
      drafts: [],
      loaded: false,
      error: null,
      busy: null,
      marked: new Set(),
    })
  },

  load: projectId => {
    Sculpt.reset()
    Sculpt.projectId = projectId
    return Sculpt.read(projectId, false)
  },

  read: (projectId, background) =>
    auth(`/project/${projectId}/drafts`, { background })
      .then(answer => {
        if (Sculpt.projectId !== projectId) return
        const was = Sculpt.job && Sculpt.job.state
        Sculpt.job = (answer && answer.job) || null
        Sculpt.drafts = (answer && answer.drafts) || []
        Sculpt.loaded = true
        Sculpt.error = null
        // A run that has just finished changed the project list and the cues.
        if (RUNNING.includes(was) && Sculpt.job && !RUNNING.includes(Sculpt.job.state)) {
          Flow.load({ force: true })
          if (Cues.projectId === projectId) Cues.load(projectId)
        }
      })
      .catch(err => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.error = `Could not load the drafts: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.schedule()
        m.redraw()
      }),

  running: () => Boolean(Sculpt.job && RUNNING.includes(Sculpt.job.state)),

  schedule: () => {
    Sculpt.stopPolling()
    const projectId = Sculpt.projectId
    if (!projectId || !Sculpt.running()) return
    Sculpt.timer = setTimeout(() => {
      Sculpt.timer = null
      if (Sculpt.projectId === projectId) Sculpt.read(projectId, true)
    }, POLL_MS)
  },

  stopPolling: () => {
    clearTimeout(Sculpt.timer)
    Sculpt.timer = null
  },

  toggle: id => {
    if (Sculpt.chosen.has(id)) Sculpt.chosen.delete(id)
    else Sculpt.chosen.add(id)
  },

  /** The value typed for a recipe's field, or the field's own default. */
  valueOf: (recipe, field) => {
    const typed = (Sculpt.values[recipe.id] || {})[field.attrs.name]
    if (typed !== undefined) return typed
    const given = field.attrs.defaultValue
    return given === undefined || given === null ? '' : String(given)
  },

  setValue: (recipe, field, value) => {
    Sculpt.values[recipe.id] = { ...(Sculpt.values[recipe.id] || {}), [field.attrs.name]: value }
  },

  /** What a run would ask for: each chosen recipe with its values. */
  request: () => ({
    recipes: Sculpt.recipes
      .filter(r => Sculpt.chosen.has(r.id))
      .map(r => ({
        recipe: r.id,
        values: Object.fromEntries((r.fields || []).map(f => [f.attrs.name, Sculpt.valueOf(r, f)])),
      })),
  }),

  /** Why a run cannot start, or '' when it can. */
  cannotRun: () => {
    const id = Sculpt.projectId
    if (!id) return 'Choose a project on the Source stage first.'
    if (Transcript.projectId === id && Transcript.loaded && !Transcript.words.length) {
      return 'Transcribe the timeline first: the recipes read its words.'
    }
    if (!Sculpt.chosen.size) return 'Tick at least one recipe.'
    if (Sculpt.running()) return 'Recipes are running over this project; wait for them to finish.'
    if (Sculpt.busy) return 'Waiting for the server…'
    return ''
  },

  /** Start a run of the chosen recipes over the open project. */
  run: () => {
    const projectId = Sculpt.projectId
    if (Sculpt.cannotRun()) return Promise.resolve()
    Sculpt.busy = 'run'
    Sculpt.error = null
    return auth(`/project/${projectId}/drafts`, { method: 'POST', body: Sculpt.request() })
      .then(answer => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.job = (answer && answer.job) || Sculpt.job
        Sculpt.schedule()
      })
      .catch(err => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.error = `Could not start the recipes: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        if (Sculpt.projectId === projectId) Sculpt.busy = null
        m.redraw()
      })
  },

  mark: id => {
    if (Sculpt.marked.has(id)) Sculpt.marked.delete(id)
    else Sculpt.marked.add(id)
  },

  markAll: () => {
    if (Sculpt.marked.size === Sculpt.drafts.length) Sculpt.marked = new Set()
    else Sculpt.marked = new Set(Sculpt.drafts.map(d => d.id))
  },

  /** Drop the marked drafts, with their cues on the source. */
  drop: () => {
    const projectId = Sculpt.projectId
    const drafts = [...Sculpt.marked]
    if (!projectId || !drafts.length || Sculpt.busy) return Promise.resolve()
    Sculpt.busy = 'drop'
    Sculpt.error = null
    return auth(`/project/${projectId}/drafts`, { method: 'DELETE', body: { drafts } })
      .then(() => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.marked = new Set()
        Flow.load({ force: true })
        if (Cues.projectId === projectId) Cues.load(projectId)
        return Sculpt.read(projectId, false)
      })
      .catch(err => {
        if (Sculpt.projectId !== projectId) return
        Sculpt.error = `Could not drop the drafts: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        if (Sculpt.projectId === projectId) Sculpt.busy = null
        m.redraw()
      })
  },
}
