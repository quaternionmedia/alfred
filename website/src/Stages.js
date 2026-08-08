import m from 'mithril'
import './styles/stages.scss'
import { auth } from './Login'
import { User } from './User'
import { Edl } from './Video'

var state = require('./Globals').state

/**
 * The four stages of the flow, as one view.
 *
 * Source -> Edit -> Render -> Deliver. They are stages of a single timeline
 * page rather than separate routes, because the timeline is the app: leaving
 * it to pick a project or to start a render is what made the previous
 * arrangement feel like four unrelated screens sharing a menu.
 *
 * Everything a stage needs is on the project, so a saved project *is* the
 * reusable pipeline -- pick it again and its source, render settings and
 * destination come back with it. Nothing is remembered for an anonymous
 * visitor, who has nowhere to save it to.
 */

export const STAGES = [
  { id: 'source', label: 'Source', hint: 'Choose a project and its material' },
  { id: 'edit', label: 'Edit', hint: 'Arrange clips on the timeline' },
  { id: 'render', label: 'Render', hint: 'Turn the timeline into a video' },
  { id: 'deliver', label: 'Deliver', hint: 'Send the finished render onward' },
]

export const DEFAULT_STAGE = 'edit'

export const Flow = {
  projects: [],
  videos: [],
  renders: [],
  destinations: ['local', 'bucket'],
  busy: false,
  error: null,

  project: () => Flow.projects.find(p => p._id === m.route.param('project')),

  // The URL is the state, not a copy of it.
  //
  // Mirroring the stage into a module variable and syncing it in `oninit`
  // looked fine and did not work: mithril reuses a component across parameter
  // changes, so oninit runs once and every ?stage= after the first was
  // ignored. Reading the route on each draw removes the thing that could
  // disagree, and makes a reload, a bookmark and a shared link all land where
  // the person left off.
  stage: () => {
    const requested = m.route.param('stage')
    return STAGES.some(s => s.id === requested) ? requested : DEFAULT_STAGE
  },

  go: id => {
    m.route.set(m.route.get().split('?')[0], {
      ...m.route.param(),
      stage: id,
    })
  },

  load: () => {
    if (!User.loggedIn) return
    auth('/project')
      .then(p => {
        Flow.projects = p
      })
      .catch(() => {})
    auth('/videos')
      .then(v => {
        Flow.videos = v
      })
      .catch(() => {})
    Flow.loadRenders()
  },

  chosenDestination: () => {
    const project = Flow.project()
    return (project && project.destination) || 'local'
  },

  /** Save a stage's settings onto the project, so the flow is reusable.
   *
   * Silent on failure by design: a saved preference is a convenience, and
   * losing it should not interrupt a render that already succeeded. An
   * anonymous visitor has no project to save to and skips this entirely.
   */
  remember: patch => {
    const id = m.route.param('project')
    if (!id || !User.loggedIn) return
    // `/settings`, not a PUT to the project itself. The crud router's update
    // replaces the whole document, so a partial body writes null over every
    // field it omits -- which is not theoretical: doing that here wiped a
    // project's name and logic, and every subsequent GET of it answered 500,
    // because writes are not validated and reads are.
    auth(`/project/${id}/settings`, { method: 'PUT', body: patch })
      .then(updated => {
        Flow.projects = Flow.projects.map(p => (p._id === id ? updated : p))
        m.redraw()
      })
      .catch(() => {})
  },

  loadRenders: () =>
    auth('/render')
      .then(r => {
        Flow.renders = r
        m.redraw()
      })
      .catch(() => {}),
}

/** The stage rail. Always visible, so the whole flow is legible at a glance. */
export const StageRail = () => ({
  view: () =>
    m(
      'nav.stagerail',
      { role: 'tablist' },
      STAGES.map((stage, i) =>
        m(
          'button.stage',
          {
            id: `stage-${stage.id}`,
            role: 'tab',
            class: Flow.stage() === stage.id ? 'active' : '',
            // The strings, not a boolean. `aria-selected` is an enumerated
            // attribute, and mithril renders `true` as a bare `aria-selected=""`
            // -- the HTML boolean form -- which conveys no state to a screen
            // reader at all. `false` would drop the attribute entirely, which
            // is worse: an unselected tab becomes indistinguishable from an
            // element that never had the attribute.
            'aria-selected': Flow.stage() === stage.id ? 'true' : 'false',
            title: stage.hint,
            onclick: () => Flow.go(stage.id),
          },
          [m('span.stagenum', `${i + 1}`), m('span.stagelabel', stage.label)]
        )
      )
    ),
})

const Empty = message => m('p.stageempty', message)

/** Stage 1 -- pick the project, see what material is available to it. */
const SourcePanel = {
  view: () => {
    const current = m.route.param('project')
    return m('.stagepanel#panel-source', [
      m('h3', 'Project'),
      Flow.projects.length
        ? m(
            'ul.projectpicker',
            Flow.projects.map(p =>
              m(
                'li',
                m(
                  'button.projectchoice',
                  {
                    class: p._id === current ? 'active' : '',
                    onclick: () => {
                      m.route.set('/otto', { project: p._id, stage: 'edit' })
                    },
                  },
                  [
                    m('span.projectname', p.name || '(unnamed)'),
                    m(
                      'span.projectclips',
                      `${((p.edl || {}).clips || []).length} clips`
                    ),
                  ]
                )
              )
            )
          )
        : Empty('No projects yet.'),
      m('h3', 'Material'),
      Flow.videos.length
        ? m(
            'ul.medialist',
            Flow.videos.map(v => m('li.mediaitem', typeof v === 'string' ? v : v.name))
          )
        : Empty('No media on the server. `./al demo` downloads some.'),
    ])
  },
}

/** Stage 3 -- queue a render of what is on the timeline. */
const RenderPanel = {
  view: () => {
    const project = Flow.project()
    return m('.stagepanel#panel-render', [
      m('h3', 'Render'),
      // Defaults come from the project when it has an opinion, so reopening
      // one brings back the size it renders at rather than asking again.
      m('.renderfields', [
        m('label', [
          'Width',
          m('input#render-width', {
            type: 'number',
            value: (project && project.render_settings && project.render_settings.width) || state.width(),
          }),
        ]),
        m('label', [
          'Height',
          m('input#render-height', {
            type: 'number',
            value: (project && project.render_settings && project.render_settings.height) || state.height(),
          }),
        ]),
      ]),
      m(
        'button#queue-render.primary',
        {
          disabled: Flow.busy || !Edl.edl.length,
          onclick: () => {
            Flow.busy = true
            Flow.error = null
            auth('/render', {
              method: 'POST',
              body: {
                edl: { clips: Edl.edl, duration: Edl.duration() },
                name: project ? project.name : 'untitled',
                project: project ? project.name : 'untitled',
                project_id: m.route.param('project'),
                width: Number(document.getElementById('render-width').value),
                height: Number(document.getElementById('render-height').value),
                duration: Edl.duration(),
              },
            })
              .then(() => {
                Flow.busy = false
                // Remember what this project renders at. This is the whole of
                // "reusable pipeline": the settings live on the project, so
                // picking it again is picking the pipeline.
                Flow.remember({
                  render_settings: {
                    width: Number(document.getElementById('render-width').value),
                    height: Number(document.getElementById('render-height').value),
                  },
                })
                Flow.loadRenders()
                Flow.go('deliver')
              })
              .catch(e => {
                Flow.busy = false
                Flow.error = 'Could not queue the render'
                m.redraw()
              })
          },
        },
        Flow.busy ? 'Queueing…' : 'Queue render'
      ),
      // A timeline with no clips cannot be rendered, and saying so beats a
      // button that looks available and fails.
      Edl.edl.length ? null : Empty('Add a clip on the Edit stage first.'),
      Flow.error ? m('p.stageerror', Flow.error) : null,
    ])
  },
}

/** Stage 4 -- send a finished render to its destination. */
const DeliverPanel = {
  oninit: () => Flow.loadRenders(),
  view: () =>
    m('.stagepanel#panel-deliver', [
      m('h3', 'Deliver'),
      m('label', [
        'Destination',
        m(
          'select#destination',
          Flow.destinations.map(d =>
            m(
              'option',
              { value: d, selected: d === Flow.chosenDestination() },
              d
            )
          )
        ),
      ]),
      Flow.renders.length
        ? m(
            'ul.renderlist',
            Flow.renders.slice(0, 8).map(r =>
              m('li.renderitem', [
                m('span.rendername', r.filename || r.name || r._id),
                r.destination
                  ? m('span.delivered', `delivered → ${r.destination}`)
                  : m(
                      'button.deliver',
                      {
                        onclick: () => {
                          const destination =
                            document.getElementById('destination').value
                          auth(
                            `/render/${r._id}/deliver?destination=${destination}`,
                            { method: 'POST' }
                          )
                            .then(() => {
                              Flow.remember({ destination })
                              Flow.loadRenders()
                            })
                            .catch(() => {
                              Flow.error = 'Delivery failed'
                              m.redraw()
                            })
                        },
                      },
                      'Deliver'
                    ),
              ])
            )
          )
        : Empty('Nothing rendered yet.'),
      Flow.error ? m('p.stageerror', Flow.error) : null,
    ]),
}

/** The panel for the current stage. Edit has none -- it *is* the timeline. */
export const StagePanel = () => ({
  oninit: () => Flow.load(),
  view: () => {
    const stage = Flow.stage()
    if (stage === 'source') return m(SourcePanel)
    if (stage === 'render') return m(RenderPanel)
    if (stage === 'deliver') return m(DeliverPanel)
    // Edit has no panel: it *is* the timeline, which is always mounted below.
    return null
  },
})
