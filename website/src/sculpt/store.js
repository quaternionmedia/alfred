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
 *
 * A recipe is edited here too: a copy of any recipe, or one of the account's
 * own, with its steps and their parameters, checked by `POST /recipes/check`
 * and stored by `POST` or `PUT /recipes`; the operations a step may name come
 * from `GET /recipes/operations`.
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

  // The operations a step may name (`GET /recipes/operations`).
  operations: [],
  operationsLoaded: false,
  // The recipe being edited: `{id, name, label, description, fields, steps}`,
  // `id` null for one not stored yet; each step `{op, params}`, every
  // parameter as the text typed, `$knob` for a knob it reads.
  editing: null,
  // What the server said of it: 'ok' after a check passed, `{detail, step}`
  // after a refusal, the step counted from 1 and 0 for none named.
  verdict: null,

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

  // --- editing a recipe -------------------------------------------------------

  loadOperations: () => {
    if (Sculpt.operationsLoaded) return
    Sculpt.operationsLoaded = true
    auth('/recipes/operations')
      .then(operations => {
        Sculpt.operations = operations || []
      })
      .catch(() => {
        Sculpt.operationsLoaded = false
      })
  },

  operation: name => Sculpt.operations.find(o => o.name === name) || null,

  /** A stored step as the editor holds it: each parameter as text, `$knob` for a knob it reads. */
  stepFrom: step => {
    const params = {}
    Object.entries(step || {}).forEach(([key, value]) => {
      if (key === 'op') return
      const reads = value && typeof value === 'object' && typeof value.var === 'string'
      params[key] = reads ? `$${value.var}` : String(value)
    })
    return { op: step.op, params }
  },

  /**
   * A step as the api takes it: a blank parameter left out, so the operation's
   * own value holds; `$knob` as a read of that knob; a number or a boolean by
   * the parameter's kind, and the rest as typed.
   */
  stepTo: step => {
    const out = { op: step.op }
    const operation = Sculpt.operation(step.op)
    Object.entries(step.params || {}).forEach(([key, text]) => {
      const typed = String(text == null ? '' : text).trim()
      if (!typed) return
      if (typed.startsWith('$')) {
        out[key] = { var: typed.slice(1) }
        return
      }
      const kind = operation && operation.parameters[key] ? operation.parameters[key].kind : 'text'
      if ((kind === 'number' || kind === 'integer') && typed !== '' && Number.isFinite(Number(typed))) {
        out[key] = Number(typed)
      } else if (kind === 'boolean' && ['true', 'false'].includes(typed.toLowerCase())) {
        out[key] = typed.toLowerCase() === 'true'
      } else {
        out[key] = typed
      }
    })
    return out
  },

  /** Start editing: a copy of `recipe` as a new one of mine, or, with `own`, the recipe itself. */
  edit: (recipe, own) => {
    Sculpt.loadOperations()
    Sculpt.editing = {
      id: own ? recipe.id : null,
      name: own ? recipe.name : `${recipe.name}-copy`,
      label: own ? recipe.label || recipe.name : `${recipe.label || recipe.name} (copy)`,
      description: recipe.description || '',
      fields: JSON.parse(JSON.stringify(recipe.fields || [])),
      steps: (recipe.steps || []).map(Sculpt.stepFrom),
    }
    Sculpt.verdict = null
  },

  cancelEdit: () => {
    Sculpt.editing = null
    Sculpt.verdict = null
  },

  setEditing: (key, value) => {
    Sculpt.editing[key] = value
    Sculpt.verdict = null
  },

  setStepOp: (index, op) => {
    Sculpt.editing.steps[index] = { op, params: {} }
    Sculpt.verdict = null
  },

  setParam: (index, name, text) => {
    Sculpt.editing.steps[index].params[name] = text
    Sculpt.verdict = null
  },

  addStep: op => {
    if (op) Sculpt.editing.steps.push({ op, params: {} })
    Sculpt.verdict = null
  },

  removeStep: index => {
    Sculpt.editing.steps.splice(index, 1)
    Sculpt.verdict = null
  },

  moveStep: (index, by) => {
    const steps = Sculpt.editing.steps
    const to = index + by
    if (to < 0 || to >= steps.length) return
    ;[steps[index], steps[to]] = [steps[to], steps[index]]
    Sculpt.verdict = null
  },

  /** The recipe being edited as `POST /recipes` takes it. */
  body: () => {
    const e = Sculpt.editing
    return {
      name: String(e.name || '').trim(),
      label: String(e.label || '').trim(),
      description: String(e.description || '').trim(),
      fields: e.fields,
      steps: e.steps.map(Sculpt.stepTo),
    }
  },

  /** A refusal as a verdict: its sentence, and the step it names, from 1, or 0. */
  refused: err => {
    const detail = requestProblem(err) || 'no answer'
    const named = /^step (\d+)/.exec(detail)
    return { detail, step: named ? Number(named[1]) : 0 }
  },

  /** Check the recipe as saving would, without saving. */
  check: () => {
    if (!Sculpt.editing || Sculpt.busy) return Promise.resolve()
    Sculpt.busy = 'check'
    return auth('/recipes/check', { method: 'POST', body: Sculpt.body() })
      .then(() => {
        Sculpt.verdict = 'ok'
      })
      .catch(err => {
        Sculpt.verdict = Sculpt.refused(err)
      })
      .then(() => {
        Sculpt.busy = null
        m.redraw()
      })
  },

  /** Store the recipe being edited as mine, new or replaced, and tick it. */
  save: () => {
    if (!Sculpt.editing || Sculpt.busy) return Promise.resolve()
    const own = Sculpt.editing.id
    Sculpt.busy = 'save'
    return auth(own ? `/recipes/${own}` : '/recipes', {
      method: own ? 'PUT' : 'POST',
      body: Sculpt.body(),
    })
      .then(saved => {
        Sculpt.editing = null
        Sculpt.verdict = null
        Sculpt.chosen = new Set([saved.id])
        delete Sculpt.values[saved.id]
        Sculpt.loadRecipes({ force: true })
      })
      .catch(err => {
        Sculpt.verdict = Sculpt.refused(err)
      })
      .then(() => {
        Sculpt.busy = null
        m.redraw()
      })
  },

  /** Delete one of mine; a draft it made keeps naming it. */
  remove: id => {
    if (Sculpt.busy) return Promise.resolve()
    Sculpt.busy = 'remove'
    Sculpt.error = null
    return auth(`/recipes/${id}`, { method: 'DELETE' })
      .then(() => {
        Sculpt.chosen.delete(id)
        if (Sculpt.editing && Sculpt.editing.id === id) Sculpt.cancelEdit()
        Sculpt.loadRecipes({ force: true })
      })
      .catch(err => {
        Sculpt.error = `Could not delete the recipe: ${requestProblem(err) || 'no answer'}`
      })
      .then(() => {
        Sculpt.busy = null
        m.redraw()
      })
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
