import m from 'mithril'
import { Edl } from '../Video'
import { Magnussens } from '../Magnussens'
import { queueRender, renderSize, timelineRender } from '../RenderRequest'
import { Health, RendererNotice } from '../Health'
import { requestProblem } from '../Problem'
import { AsyncButton, Empty, Flow, FlowPanel } from '../Stages'

/** Stage 3 -- queue a render of what is on the timeline. */
const RenderPanel = {
  // Whether anything is there to render the timeline, while it is on offer.
  oninit: () => Health.watch('render'),
  onupdate: () => Health.catchUp(),
  onremove: () => Health.unwatch('render'),
  view: () => {
    const project = Flow.project()

    // A project drives a render one of two ways, and which one is a property
    // of the project rather than a choice the person makes.
    //
    // Projects with `fields` and `logic` are form-driven: you fill in a form
    // and the logic compiles it into clips. That lived at #!/form -- a route
    // with no stage rail, reachable from the project list and unable to get
    // back to it, and which rendered a submittable form even with no project
    // at all. It is the Render stage for those projects.
    const formDriven = project && (project.fields || []).length > 0
    if (formDriven) {
      return m('.stagepanel#panel-render', [
        m('h3', 'Render from the project form'),
        m(RendererNotice),
        m('p.stagenote', [
          'This project builds its clips from a form rather than from the ',
          'timeline. ',
          m(
            'button.linklike',
            { onclick: () => Flow.go('edit') },
            'Open the timeline instead'
          ),
        ]),
        m('.formhost', m(Magnussens)),
      ])
    }

    // Defaults come from the project when it has an opinion, so reopening one
    // brings back the size it renders at rather than asking again.
    //
    // What was typed is held here rather than left in the input. The inputs
    // were uncontrolled, and mithril writes `value` back on every redraw -- so
    // any redraw between typing a size and pressing the button (a list
    // arriving, a render's progress) quietly restored the project's size, and
    // the render went out at a size nobody chose. Typed values win until the
    // project changes.
    const draftFor = m.route.param('project') || ''
    if (Flow.draft.for !== draftFor) Flow.draft = { for: draftFor, size: {} }
    const size = { ...renderSize(project), ...Flow.draft.size }
    const sizeInput = key => ({
      type: 'number',
      min: 2,
      step: 2,
      value: size[key],
      oninput: e => {
        Flow.draft.size = { ...Flow.draft.size, [key]: e.target.value }
      },
    })

    return m('.stagepanel#panel-render', [
      m('h3', 'Render'),
      // Said before the button, not after the render has sat queued for a
      // while: a render queued now will wait for a renderer to start.
      m(RendererNotice),
      m('.renderfields', [
        m('label', ['Width', m('input#render-width', sizeInput('width'))]),
        m('label', ['Height', m('input#render-height', sizeInput('height'))]),
      ]),
      m(AsyncButton, {
        id: 'queue-render',
        class: 'primary',
        busy: Flow.busy,
        disabled: !Edl.edl.length,
        label: 'Queue render',
        busyLabel: 'Queueing…',
        onclick: () => {
          const chosen = { width: Number(size.width), height: Number(size.height) }
          Flow.busy = true
          Flow.error = null
          // The same request the toolbar's Render button sends, built in one
          // place: every clip placed by an explicit start (see timelineEdl).
          queueRender(
            timelineRender({ project, projectId: m.route.param('project'), ...chosen })
          )
            .then(() => {
              Flow.busy = false
              // Remember what this project renders at. This is the whole of
              // "reusable pipeline": the settings live on the project, so
              // picking it again is picking the pipeline.
              Flow.remember({ render_settings: chosen })
              Flow.loadRenders()
              Flow.go('deliver')
            })
            .catch(e => {
              Flow.busy = false
              const why = requestProblem(e)
              Flow.error = why
                ? `Could not queue the render: ${why}`
                : 'Could not queue the render'
              m.redraw()
            })
        },
      }),
      // A timeline with no clips cannot be rendered, and saying so beats a
      // button that looks available and fails.
      Edl.edl.length ? null : Empty('Add a clip on the Edit stage first.'),
      Flow.error ? m('p.stageerror', Flow.error) : null,
    ])
  },
}

/** The Render stage, loading the flow's lists as the stage panel did. */
export const Render = FlowPanel(RenderPanel)

export default Render
