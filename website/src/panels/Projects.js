import m from 'mithril'
import { auth } from '../Login'
import { TemplateEditor } from '../TemplateEditor'
import { Empty, Flow, FlowPanel, Generate } from '../Stages'

/**
 * Projects: the Source stage's project picker, as a panel.
 *
 * The first half of what the Source stage showed; the material it listed
 * beside the projects is the Media & templates panel (Media.js). What this
 * says about itself is as the stage said it:
 *
 * Stage 1 -- pick the project, see what material is available to it.
 *
 * This is now the only project selector in the app.
 *
 * There were two, fetching /project independently and rendering it
 * differently: this picker, and the table at #!/projects. Two components with
 * separate state for one list means they disagree -- generate a project here
 * and the table did not know, and neither told the other when a selection
 * changed. `Flow` is the single source now, and #!/projects redirects here.
 *
 * It absorbs what the table offered rather than dropping it: the edit-template
 * and create-video actions per project, which were the table's only reason to
 * exist beyond listing.
 */
const ProjectsPanel = {
  // Re-read on entering the stage.
  //
  // `Flow.load` caches, so it does not refetch on every draw -- but the cache
  // is module state and a hash navigation keeps it, so arriving at Source
  // after creating a project elsewhere showed the list from before. This panel
  // is the one place freshness matters, and it is mounted anew each time the
  // stage is entered, so this is once per visit rather than once per frame.
  oninit: () => Flow.load({ force: true }),
  view: () => {
    const current = m.route.param('project')
    const matches = Flow.matchingProjects()

    return m('.stagepanel#panel-source', [
      m('.panelhead', [
        m('h3', `Project${Flow.projects.length ? ` (${Flow.projects.length})` : ''}`),
        // A filter rather than pagination: the list is small enough to render
        // whole, and typing a name beats scrolling for one.
        Flow.projects.length > 3
          ? m('input#project-filter.filter', {
              type: 'search',
              placeholder: 'Filter projects',
              value: Flow.filter,
              oninput: e => {
                Flow.filter = e.target.value
              },
            })
          : null,
      ]),

      Flow.projects.length
        ? matches.length
          ? m(
              'ul.projectpicker',
              matches.map(p => m(ProjectCard, { project: p, current }))
            )
          : Empty(`Nothing matches "${Flow.filter}".`)
        : Generate(
            'No projects yet.',
            'Generate a demo project',
            () => auth('/demo/project', { method: 'POST' }),
            'project'
          ),

      // A project id in the URL that names nothing is worth saying out loud.
      // It arrives from a stale bookmark or a hand-edited link, and silently
      // ignoring it leaves the stages looking empty for no stated reason.
      current && Flow.projects.length && !Flow.project()
        ? m('p.stagewarn#unknown-project', [
            'No project with that id. ',
            m(
              'button.linklike',
              { onclick: () => m.route.set('/', { stage: 'source' }) },
              'Clear it'
            ),
          ])
        : null,

      // The template editor, which used to be a route of its own at #!/editor
      // with no stage rail and no timeline -- a second interface reachable
      // from this one and unable to get back to it. It is a property of the
      // selected project, so it belongs beside the project you selected.
      // No `key` here. A keyed vnode among unkeyed siblings makes mithril
      // reject the whole fragment -- "vnodes must either all have keys or none
      // have keys" -- and it throws during render, so this entire panel
      // produced no DOM at all. Not a subtle degradation: no project list, no
      // media, no warning above, and a timeline that stayed empty because the
      // panel that populates it never rendered. The key was there to reset the
      // editor when the selection changed, which ProjectTemplate now does by
      // watching the id itself.
      current ? m(ProjectTemplate) : null,
    ])
  },
}

/** The selected project's logic and fields, collapsed until asked for.
 *
 * Collapsed because it is reference material: most visits to this stage are to
 * pick a project, not to inspect one. Open, it is the whole of what #!/editor
 * showed.
 */
const ProjectTemplate = () => {
  let open = false
  let shownFor = null

  return {
    view: () => {
      // Collapse when the selection moves on. Carrying an open editor from one
      // project to the next shows the new project's fields under the previous
      // one's heading, which reads as the edit having followed you across.
      const current = m.route.param('project')
      if (current !== shownFor) {
        shownFor = current
        open = false
      }

      return m('.projecttemplate', [
        m(
          'button.disclosure#template-toggle',
          {
            onclick: () => (open = !open),
            'aria-expanded': open ? 'true' : 'false',
          },
          [m('i.material-icons', open ? 'expand_more' : 'chevron_right'), 'Template']
        ),
        open ? m('.templatebody', m(TemplateEditor)) : null,
      ])
    },
  }
}

/** One project, with everything known about it and everything you can do. */
const ProjectCard = () => ({
  view: vnode => {
    const p = vnode.attrs.project
    const clips = ((p.edl || {}).clips || []).length
    const duration = (p.edl || {}).duration
    const size = p.render_settings
      ? `${p.render_settings.width}×${p.render_settings.height}`
      : null

    return m('li.projectrow', { class: p._id === vnode.attrs.current ? 'active' : '' }, [
      m(
        'button.projectchoice',
        {
          title: 'Open this project on the timeline',
          class: p._id === vnode.attrs.current ? 'active' : '',
          onclick: () => m.route.set('/', { project: p._id, stage: 'edit' }),
        },
        [
          m('span.projectname', p.name || '(unnamed)'),
          // What the old table could not show: whether there is anything to
          // edit, how long it runs, and what it last rendered at.
          m('span.projectmeta', [
            m('span.projectclips', `${clips} clip${clips === 1 ? '' : 's'}`),
            duration ? m('span.projectduration', `${duration}s`) : null,
            size ? m('span.projectsize', size) : null,
            p.destination ? m('span.projectdest', `→ ${p.destination}`) : null,
          ]),
        ]
      ),
      // Carried over from the projects table, which was the only place these
      // lived.
      m('.projectactions', [
        // Both actions stay inside the flow. They used to leave it for
        // #!/editor and #!/form, which had no rail and no way back to the
        // project you had just been looking at.
        m(
          'button.iconaction',
          {
            title: 'Edit the template for this project',
            onclick: () => m.route.set('/', { project: p._id, stage: 'source' }),
          },
          m('i.material-icons', 'edit')
        ),
        m(
          'button.iconaction',
          {
            title: 'Create a video from this project',
            onclick: () => m.route.set('/', { project: p._id, stage: 'render' }),
          },
          m('i.material-icons', 'video_call')
        ),
      ]),
    ])
  },
})

/** The project picker, loading the flow's lists as the stage panel did. */
export const Projects = FlowPanel(ProjectsPanel)

export default Projects
