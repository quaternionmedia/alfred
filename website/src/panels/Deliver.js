import m from 'mithril'
import { auth } from '../Login'
import { Health, RendererNotice } from '../Health'
import { blobProblem, downloadRender } from '../Download'
import { requestProblem } from '../Problem'
import { renderState } from '../RenderStatus'
import {
  AsyncButton,
  Empty,
  Flow,
  FlowPanel,
  LiveList,
  VISIBLE_RENDERS,
  current,
} from '../Stages'

/** Stage 4 -- send a finished render to its destination.
 *
 * The only render list in the app, for the same reason as the project picker:
 * there were two, fetching /render separately, and they could not agree.
 * #!/renders redirects here.
 *
 * It carries what the renders table showed -- project, duration, size, status
 * and progress -- rather than dropping those to keep the panel small. A person
 * on this stage is deciding which render to send somewhere, and the answer
 * depends on all of it.
 */
const DeliverPanel = {
  oninit: () => {
    LiveList.start()
    Flow.loadRenders()
    Health.watch('deliver')
  },
  onupdate: () => Health.catchUp(),
  onremove: () => {
    LiveList.stop()
    Health.unwatch('deliver')
  },
  view: () =>
    m('.stagepanel#panel-deliver', [
      m('.panelhead', [
        m('h3', `Deliver${Flow.renders.length ? ` (${Flow.renders.length})` : ''}`),
        m('label.inline', [
          'Destination',
          m(
            'select#destination',
            Flow.destinations.map(d =>
              m('option', { value: d, selected: d === Flow.chosenDestination() }, d)
            )
          ),
        ]),
      ]),

      // Why a queued render is not moving, where the queued renders are.
      m(RendererNotice),

      Flow.renders.length
        ? m(
            'ul.renderlist',
            // Keyed, so a new render arriving at the top is a new row rather
            // than every row below it being repainted with its neighbour.
            Flow.renders
              .slice(0, VISIBLE_RENDERS)
              .map(r => m(RenderRow, { key: r._id, render: r }))
          )
        : Empty('Nothing rendered yet. Queue one from the Render stage.'),

      Flow.error ? m('p.stageerror', Flow.error) : null,
    ]),
}

/** One render, with its state and the actions available to it. */
const RenderRow = () => ({
  view: vnode => {
    const r = current(vnode.attrs.render)
    const state = renderState(r)
    const progress =
      typeof r.progress === 'number' ? Math.max(0, Math.min(100, Math.round(r.progress))) : null
    const done = state === 'rendered'
    const failed = state === 'failed'
    const working = !done && !failed

    const label = r.project || r.name || r._id

    const row = {
      class: failed ? 'failed' : done ? 'done' : 'working',
      'data-render': r._id,
      'data-state': state,
    }

    return m('li.renderitem', row, [
      m('span.rendername', { title: r.filename || '' }, [
        label,
        r.description ? m('span.renderdesc', r.description) : null,
      ]),

      m('span.rendermeta', [
        r.width && r.height ? m('span', `${r.width}×${r.height}`) : null,
        r.duration ? m('span', `${Math.round(r.duration)}s`) : null,
        // Status and progress were only in the old table, and they are what
        // tells you whether a render can be delivered at all. They move now:
        // a watched render is polled, and the stage refreshes the rest.
        m('span.renderstatus', state),
        working
          ? m('progress.renderbar', {
              max: 100,
              // No value while queued: an indeterminate bar says "waiting"
              // without claiming a percentage nobody has reported.
              value: state === 'rendering' && progress !== null ? progress : undefined,
              'aria-label': `${label} progress`,
            })
          : null,
        working && progress !== null ? m('span.renderprogress', `${progress}%`) : null,
      ]),

      // Why it failed, where the failure is. This was nowhere in the
      // interface; a failed render was a red word and nothing else.
      failed && r.error ? m('span.rendererror', { title: r.error }, r.error) : null,

      m('span.renderactions', [downloadAction(r, done), deliverAction(r, done)]),
    ])
  },
})

/** Download the file -- for every finished render, delivered or not.
 *
 * Getting the video back used to mean delivering it to `local` and then
 * finding the file on the server's disk. A download needs no destination and
 * no access to the machine, so getting the video back works the same whether
 * or not the server has cloud storage.
 */
const downloadAction = (r, done) =>
  m(AsyncButton, {
    class: 'download',
    busy: Flow.downloading === r._id,
    disabled: !done,
    title: done ? 'Download this render' : 'Not finished yet',
    label: 'Download',
    busyLabel: 'Downloading…',
    onclick: () => {
      Flow.downloading = r._id
      Flow.error = null
      downloadRender(r)
        .then(() => {
          Flow.downloading = null
          m.redraw()
        })
        .catch(err =>
          blobProblem(err).then(why => {
            Flow.downloading = null
            Flow.error = why
              ? `Could not download it: ${why}`
              : err.code === 409
                ? 'Could not download it: the render has no file yet'
                : 'Could not download it'
            m.redraw()
          })
        )
    },
  })

/** Deliver, or where it was delivered to. */
const deliverAction = (r, done) =>
  r.destination
    ? m('span.delivered', `delivered → ${r.destination}`)
    : m(AsyncButton, {
        class: 'deliver',
        busy: Flow.delivering === r._id,
        // A render that has not finished has no file to send, and a button
        // that fails is worse than one that explains itself.
        disabled: !done,
        title: done ? 'Send this render to the chosen destination' : 'Not finished yet',
        label: 'Deliver',
        busyLabel: 'Delivering…',
        onclick: () => {
          const destination = document.getElementById('destination').value
          // Per-render, not a single flag: several rows each have a button,
          // and one shared flag would spin all of them.
          Flow.delivering = r._id
          auth(`/render/${r._id}/deliver?destination=${destination}`, {
            method: 'POST',
          })
            .then(() => {
              Flow.delivering = null
              Flow.remember({ destination })
              Flow.loadRenders()
            })
            .catch(e => {
              Flow.delivering = null
              const why = requestProblem(e)
              Flow.error = why ? `Delivery failed: ${why}` : 'Delivery failed'
              m.redraw()
            })
        },
      })

/** The Deliver stage, loading the flow's lists as the stage panel did. */
export const Deliver = FlowPanel(DeliverPanel)

export default Deliver
