import m from 'mithril'
import { Sculpt } from '../sculpt/store'
import { Transcript } from '../captions/transcript'
import { User } from '../User'
import { AsyncButton, Empty, Flow, FlowPanel } from '../Stages'
import '../styles/sculpt.scss'

/**
 * The Sculpt stage's two panels: the recipes to run over the open project,
 * each with its knobs, and the drafts a run left, each opening on Edit.
 * Behaviour: docs/drafts.md.
 */

const projectId = () => m.route.param('project')

const seconds = n => `${Math.round(Number(n) || 0)} s`
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

const JOB_SAYS = {
  queued: () => 'Queued: the recipes are waiting for the worker…',
  running: () => 'Running the recipes over the timeline…',
  done: job =>
    `Done: ${plural(job.made ?? 0, 'draft')} made` +
    (job.notes && job.notes.length ? `. ${job.notes.join(' ')}` : '.'),
  failed: job => `The recipes failed: ${job.error || 'no reason was given'}`,
}

/** The open project's source, when it is a draft: `{id, name}`, else null. */
const sourceOf = () => {
  const project = Flow.project()
  const from = project && project.source && project.source.project
  if (!from) return null
  const source = Flow.projects.find(p => p._id === from)
  return { id: from, name: (source && source.name) || 'its source' }
}

/** A draft's way back: the project it was cut from, on Sculpt. */
const SourceLine = {
  view: ({ attrs: { source, id } }) =>
    m(`p.sculptnote#${id}`, [
      `This is a draft of ${source.name}. `,
      m(
        'button.linklike',
        { type: 'button', onclick: () => m.route.set('/', { project: source.id, stage: 'sculpt' }) },
        'Open the source'
      ),
    ]),
}

/** Where the last run got to. */
const JobLine = {
  view: () => {
    const job = Sculpt.job
    if (!job || !JOB_SAYS[job.state]) return null
    return m(
      'p.sculptjob#sculpt-job',
      { class: job.state, 'data-state': job.state, role: 'status' },
      JOB_SAYS[job.state](job)
    )
  },
}

/** One recipe: ticked or not, and its knobs when ticked. */
const RecipeRow = {
  view: ({ attrs: { recipe } }) => {
    const chosen = Sculpt.chosen.has(recipe.id)
    return m('li.recipe', { class: chosen ? 'chosen' : '', 'data-recipe': recipe.id }, [
      m('label.recipehead', [
        m('input.recipetick', {
          type: 'checkbox',
          id: `recipe-${recipe.id}`,
          checked: chosen,
          onchange: () => Sculpt.toggle(recipe.id),
        }),
        m('span.recipelabel', recipe.label || recipe.name),
        recipe.builtin ? null : m('span.recipemine', 'yours'),
      ]),
      recipe.description ? m('p.recipeabout', recipe.description) : null,
      chosen && (recipe.fields || []).length
        ? m(
            '.recipeknobs',
            recipe.fields.map(field =>
              m('label.recipeknob', [
                m('span.recipeknobtext', field.attrs.text || field.attrs.name),
                m('input', {
                  type: 'text',
                  id: `recipe-${recipe.id}-${field.attrs.name}`,
                  name: field.attrs.name,
                  value: Sculpt.valueOf(recipe, field),
                  oninput: e => Sculpt.setValue(recipe, field, e.target.value),
                }),
              ])
            )
          )
        : null,
    ])
  },
}

const RecipesPanel = {
  oninit: () => {
    Sculpt.loadRecipes()
    if (User.loggedIn) {
      Sculpt.ensure(projectId())
      Transcript.ensure(projectId())
    }
  },
  onupdate: () => {
    if (User.loggedIn) {
      Sculpt.ensure(projectId())
      Transcript.ensure(projectId())
    }
  },
  view: () => {
    const id = projectId()
    const blocker = Sculpt.cannotRun()
    return m('.stagepanel.sculptpanel#panel-recipes', [
      m('.panelhead', [
        m('h3', `Recipes${Sculpt.recipes.length ? ` (${Sculpt.recipes.length})` : ''}`),
        m(AsyncButton, {
          id: 'sculpt-run',
          class: 'primary',
          busy: Sculpt.busy === 'run' || Sculpt.running(),
          disabled: Boolean(blocker),
          title: blocker || 'Run the ticked recipes over this project and leave their drafts',
          label: 'Sculpt',
          busyLabel: Sculpt.running() ? 'Sculpting…' : 'Starting…',
          onclick: () => Sculpt.run(),
        }),
      ]),
      m(
        'p.stagehint',
        id
          ? 'Tick the recipes to run, set their knobs, then Sculpt. Each draft opens on Edit.'
          : 'Choose a project on the Source stage to sculpt it.'
      ),
      sourceOf() ? m(SourceLine, { source: sourceOf(), id: 'sculpt-source' }) : null,
      blocker && id && !sourceOf() ? m('p.sculptnote#sculpt-blocker', blocker) : null,
      Sculpt.recipesError ? m('p.stageerror', Sculpt.recipesError) : null,
      Sculpt.error ? m('p.stageerror#sculpt-error', { role: 'alert' }, Sculpt.error) : null,
      id ? m(JobLine) : null,
      Sculpt.recipes.length
        ? m(
            'ul.recipelist',
            Sculpt.recipes.map(recipe => m(RecipeRow, { key: recipe.id, recipe }))
          )
        : Sculpt.recipesError
          ? null
          : Empty('Loading the recipes…'),
    ])
  },
}

/** One draft: tick it to drop, or open it on Edit. */
const DraftRow = {
  view: ({ attrs: { draft } }) => {
    const source = draft.source || {}
    const scores = Object.entries(source.scores || {})
      .map(([name, value]) => `${name} ${Number(value).toFixed(2)}`)
      .join(', ')
    const recipe = Sculpt.recipes.find(r => r.id === source.recipe)
    return m('li.draft', { 'data-draft': draft.id }, [
      m('input.draftmark', {
        type: 'checkbox',
        'aria-label': `Mark ${draft.name || 'this draft'} to drop`,
        checked: Sculpt.marked.has(draft.id),
        onchange: () => Sculpt.mark(draft.id),
      }),
      m(
        'button.draftopen',
        {
          type: 'button',
          title: 'Open this draft on Edit',
          onclick: () => m.route.set('/', { project: draft.id, stage: 'edit' }),
        },
        [
          m('span.draftname', draft.name || '(unnamed)'),
          m('span.draftmeta', [
            draft.duration ? m('span', seconds(draft.duration)) : null,
            recipe ? m('span', recipe.label || recipe.name) : null,
            source.category ? m('span.draftcategory', source.category) : null,
            scores ? m('span.draftscores', scores) : null,
          ]),
        ]
      ),
    ])
  },
}

const DraftsPanel = {
  oninit: () => {
    Sculpt.loadRecipes()
    if (User.loggedIn) Sculpt.ensure(projectId())
  },
  onupdate: () => {
    if (User.loggedIn) Sculpt.ensure(projectId())
  },
  view: () => {
    const id = projectId()
    const count = Sculpt.drafts.length
    const marked = Sculpt.marked.size
    return m('.stagepanel.sculptpanel#panel-drafts', [
      m('.panelhead', [
        m('h3', `Drafts${count ? ` (${count})` : ''}`),
        count
          ? m('.draftactions', [
              m(
                'button#drafts-mark-all',
                {
                  type: 'button',
                  title: marked === count ? 'Untick every draft' : 'Tick every draft',
                  onclick: () => Sculpt.markAll(),
                },
                marked === count ? 'None' : 'All'
              ),
              m(AsyncButton, {
                id: 'drafts-drop',
                busy: Sculpt.busy === 'drop',
                disabled: !marked || Boolean(Sculpt.busy),
                title: marked
                  ? `Drop the ${plural(marked, 'ticked draft')}, and their cues on this project`
                  : 'Tick the drafts to drop first',
                label: marked ? `Drop ${marked}` : 'Drop',
                busyLabel: 'Dropping…',
                onclick: () => Sculpt.drop(),
              }),
            ])
          : null,
      ]),
      !id ? m('p.stagehint', 'Choose a project on the Source stage to see its drafts.') : null,
      sourceOf() ? m(SourceLine, { source: sourceOf(), id: 'drafts-source' }) : null,
      id && Sculpt.loaded && !count && !sourceOf()
        ? Empty(
            Sculpt.running()
              ? 'The recipes are running; the drafts appear here as they are made.'
              : 'No drafts yet: tick a recipe under Recipes and Sculpt.'
          )
        : null,
      count
        ? m(
            'p.stagehint',
            'Open a draft to refine it on Edit. Tick the ones you do not want, then Drop.'
          )
        : null,
      count
        ? m(
            'ul.draftlist',
            Sculpt.drafts.map(draft => m(DraftRow, { key: draft.id, draft }))
          )
        : null,
    ])
  },
}

export const Recipes = FlowPanel(RecipesPanel)
export const Drafts = FlowPanel(DraftsPanel)

/** Whether the open project is a draft: it carries where it came from. */
export const isDraft = project => Boolean(project && project.source)

export default Recipes

