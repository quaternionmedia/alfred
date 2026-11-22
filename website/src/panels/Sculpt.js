import m from 'mithril'
import { Sculpt } from '../sculpt/store'
import { Transcript } from '../captions/transcript'
import { User } from '../User'
import { AsyncButton, Empty, Flow, FlowPanel } from '../Stages'
import '../styles/sculpt.scss'

/**
 * The Sculpt stage's two panels: the recipes to run over the open project,
 * each with its knobs, and the drafts a run left, each opening on Edit. The
 * Recipes panel also edits a recipe: a copy of any, or one of the account's
 * own, step by step, checked by the server and saved as the account's.
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

/** One recipe: ticked or not, its knobs when ticked, and the ways to change it. */
const RecipeRow = {
  view: ({ attrs: { recipe } }) => {
    const chosen = Sculpt.chosen.has(recipe.id)
    const action = (suffix, title, text, onclick) =>
      m('button', { type: 'button', id: `recipe-${recipe.id}-${suffix}`, title, onclick }, text)
    return m('li.recipe', { class: chosen ? 'chosen' : '', 'data-recipe': recipe.id }, [
      m('.recipehead', [
        m('label.recipetickline', [
          m('input.recipetick', {
            type: 'checkbox',
            id: `recipe-${recipe.id}`,
            checked: chosen,
            onchange: () => Sculpt.toggle(recipe.id),
          }),
          m('span.recipelabel', recipe.label || recipe.name),
          recipe.builtin ? null : m('span.recipemine', 'yours'),
        ]),
        m('span.recipeactions', [
          action('copy', 'Copy this recipe, to change its steps', 'Copy', () =>
            Sculpt.edit(recipe, false)
          ),
          recipe.builtin
            ? null
            : action('edit', 'Change this recipe', 'Edit', () => Sculpt.edit(recipe, true)),
          recipe.builtin
            ? null
            : action('delete', 'Delete this recipe; a draft it made keeps naming it', 'Delete', () =>
                Sculpt.remove(recipe.id)
              ),
        ]),
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

/** The kinds of operation, in the order they run. */
const KINDS = ['segment', 'score', 'filter', 'edit', 'compose']

/** The operations as a select's options, grouped by kind. */
const operationOptions = () =>
  KINDS.map(kind => {
    const ops = Sculpt.operations.filter(o => o.kind === kind)
    return ops.length
      ? m(
          'optgroup',
          { label: kind },
          ops.map(o => m('option', { value: o.name, title: o.about }, o.name))
        )
      : null
  })

/** What a parameter takes, for its input's title. */
const parameterHint = p => {
  const parts = []
  if (p.kind === 'choice') parts.push(`one of ${(p.choices || []).join(', ')}`)
  else if (p.kind === 'boolean') parts.push('true or false')
  else if (p.kind === 'integer') parts.push(`a whole number from ${p.low} to ${p.high}`)
  else if (p.kind === 'number') parts.push(`a number from ${p.low} to ${p.high}`)
  else parts.push('text')
  parts.push(`blank for ${String(p.default)}`)
  parts.push('$knob to read a knob')
  return parts.join('; ')
}

/** One step of the recipe being edited: its operation, its parameters, and the refusal it earned. */
const StepRow = {
  view: ({ attrs: { step, index, problem } }) => {
    const op = Sculpt.operation(step.op)
    const n = index + 1
    const last = Sculpt.editing.steps.length - 1
    return m('li.step', { 'data-step': n, class: problem ? 'refused' : '' }, [
      m('.stephead', [
        m('span.stepnumber', `${n}.`),
        m(
          'select.stepop',
          {
            id: `recipe-editor-step-${n}-op`,
            'aria-label': `Step ${n}'s operation`,
            value: step.op,
            onchange: e => Sculpt.setStepOp(index, e.target.value),
          },
          operationOptions()
        ),
        op ? m('span.stepkind', op.kind) : null,
        m('span.stepactions', [
          m(
            'button',
            {
              type: 'button',
              title: 'Move this step up',
              disabled: index === 0,
              onclick: () => Sculpt.moveStep(index, -1),
            },
            '↑'
          ),
          m(
            'button',
            {
              type: 'button',
              title: 'Move this step down',
              disabled: index === last,
              onclick: () => Sculpt.moveStep(index, 1),
            },
            '↓'
          ),
          m(
            'button.stepremove',
            { type: 'button', title: 'Remove this step', onclick: () => Sculpt.removeStep(index) },
            'Remove'
          ),
        ]),
      ]),
      op && op.about ? m('p.stepabout', op.about) : null,
      op && Object.keys(op.parameters).length
        ? m(
            '.stepparams',
            Object.entries(op.parameters).map(([name, p]) =>
              m('label.recipeknob', [
                m('span.recipeknobtext', name),
                m('input', {
                  type: 'text',
                  id: `recipe-editor-step-${n}-${name}`,
                  placeholder: String(p.default),
                  title: parameterHint(p),
                  value: step.params[name] == null ? '' : step.params[name],
                  oninput: e => Sculpt.setParam(index, name, e.target.value),
                }),
              ])
            )
          )
        : null,
      problem ? m('p.stepproblem', { role: 'alert' }, problem) : null,
    ])
  },
}

/** The recipe being edited: its name, label and description, its steps, and Check, Save and Cancel. */
const RecipeEditor = {
  view: () => {
    const e = Sculpt.editing
    const verdict = Sculpt.verdict
    const problem = verdict && verdict !== 'ok' ? verdict : null
    const knobs = (e.fields || []).map(f => f.attrs && f.attrs.name).filter(Boolean)
    const meta = (key, text, id, wide) =>
      m(`label.recipeknob${wide ? '.wide' : ''}`, [
        m('span.recipeknobtext', text),
        m('input', {
          type: 'text',
          id,
          value: e[key],
          oninput: ev => Sculpt.setEditing(key, ev.target.value),
        }),
      ])
    return m(
      'form.recipeeditor#recipe-editor',
      {
        onsubmit: ev => {
          ev.preventDefault()
          Sculpt.save()
        },
      },
      [
        m('h4', e.id ? `Changing ${e.label || e.name}` : 'A recipe of yours'),
        m('.recipemeta', [
          meta('name', 'Name, one word', 'recipe-editor-name'),
          meta('label', 'Label', 'recipe-editor-label'),
          meta('description', 'Description', 'recipe-editor-description', true),
        ]),
        m(
          'p.sculptnote',
          (knobs.length ? `Its knobs, which a step reads as $name: ${knobs.join(', ')}. ` : '') +
            "A blank parameter is the operation's own."
        ),
        m(
          'ol.steplist',
          e.steps.map((step, index) =>
            m(StepRow, {
              key: `${index}-${step.op}`,
              step,
              index,
              problem: problem && problem.step === index + 1 ? problem.detail : null,
            })
          )
        ),
        m('label.recipeknob#recipe-editor-add-step', [
          m('span.recipeknobtext', 'Add a step'),
          m(
            'select#recipe-editor-add',
            {
              value: '',
              onchange: ev => {
                Sculpt.addStep(ev.target.value)
                ev.target.value = ''
              },
            },
            [m('option', { value: '' }, '…'), ...operationOptions()]
          ),
        ]),
        problem && !problem.step
          ? m('p.stageerror#recipe-editor-problem', { role: 'alert' }, problem.detail)
          : null,
        verdict === 'ok'
          ? m('p.sculptnote.ok#recipe-editor-ok', { role: 'status' }, 'Checked: the recipe can run.')
          : null,
        m('.recipeeditoractions', [
          m(AsyncButton, {
            id: 'recipe-editor-check',
            type: 'button',
            busy: Sculpt.busy === 'check',
            disabled: Boolean(Sculpt.busy),
            title: 'Check the recipe as saving would, without saving it',
            label: 'Check',
            busyLabel: 'Checking…',
            onclick: () => Sculpt.check(),
          }),
          m(AsyncButton, {
            id: 'recipe-editor-save',
            class: 'primary',
            type: 'submit',
            busy: Sculpt.busy === 'save',
            disabled: Boolean(Sculpt.busy),
            title: e.id ? 'Save the changes to this recipe' : 'Store this recipe as yours',
            label: e.id ? 'Save' : 'Save as mine',
            busyLabel: 'Saving…',
          }),
          m(
            'button#recipe-editor-cancel',
            { type: 'button', onclick: () => Sculpt.cancelEdit() },
            'Cancel'
          ),
        ]),
      ]
    )
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
          ? 'Tick the recipes to run, set their knobs, then Sculpt. Each draft opens on Edit. Copy a recipe to change its steps.'
          : 'Choose a project on the Source stage to sculpt it. Copy a recipe to change its steps.'
      ),
      sourceOf() ? m(SourceLine, { source: sourceOf(), id: 'sculpt-source' }) : null,
      blocker && id && !sourceOf() ? m('p.sculptnote#sculpt-blocker', blocker) : null,
      Sculpt.recipesError ? m('p.stageerror', Sculpt.recipesError) : null,
      Sculpt.error ? m('p.stageerror#sculpt-error', { role: 'alert' }, Sculpt.error) : null,
      id ? m(JobLine) : null,
      Sculpt.editing ? m(RecipeEditor) : null,
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

