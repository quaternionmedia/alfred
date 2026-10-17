import m from 'mithril'
import './styles/stages.scss'
import { auth } from './Login'
import { User } from './User'
import { Edl } from './Video'
import { TemplateEditor } from './TemplateEditor'
import { Magnussens } from './Magnussens'
import { queueRender, renderSize, timelineRender } from './RenderRequest'
import { RenderStatus, isSettled, renderState } from './RenderStatus'
import { blobProblem, downloadRender } from './Download'
import { requestProblem } from './Problem'
import { addClip, templateClip, videoClip } from './Clips'
import Bin from './Bin'

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
  // Fetched, not hardcoded. Cloud delivery is the next phase, so the server
  // currently offers only `local` -- and a destination becoming available
  // should be a server change rather than a frontend release.
  destinations: [],
  busy: false,
  error: null,
  // The Render stage's typed-but-not-yet-rendered size, for one project.
  draft: { for: null, size: {} },

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

  generating: null,
  filter: '',

  /** Projects matching the filter box, or all of them when it is empty. */
  matchingProjects: () => {
    const needle = Flow.filter.trim().toLowerCase()
    if (!needle) return Flow.projects
    return Flow.projects.filter(p => (p.name || '').toLowerCase().includes(needle))
  },

  delivering: null,
  downloading: null,

  // The most recent addition to the timeline, for the confirmation line.
  added: null,

  loaded: false,

  load: opts => {
    // Two things this has to get right, learned one at a time.
    //
    // Retry once a session exists. A restored session resolves
    // asynchronously -- `User.restore()` only sets `loggedIn` after
    // /users/me answers -- and `StagePanel.oninit` runs before that. Loading
    // only on init left every stage panel empty after a reload: no projects,
    // no media, no renders, and no error to explain it. Arriving by logging in
    // worked and arriving by refreshing did not.
    //
    // Then cache, or `onupdate` refetches on every frame. The cache is module
    // state and survives a hash navigation, so `force` exists for the cases
    // where the data has certainly changed -- entering the Source stage, or
    // having just generated something. It does not clear the lists first:
    // blanking them made the panel flash empty on every visit, which reads as
    // data being lost rather than refreshed.
    if (!User.loggedIn) return
    if (Flow.loaded && !(opts && opts.force)) return
    Flow.loaded = true

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
    auth('/destinations')
      .then(d => {
        Flow.destinations = d
        m.redraw()
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

  // Several things reload the render list now -- the stage opening, a render
  // queued or settling, the refresh while something is unfinished -- and
  // responses can arrive out of order. One that was asked for before the list
  // on screen is older than it, and must not replace it.
  rendersAsked: 0,
  rendersShown: 0,

  loadRenders: () => {
    const asked = ++Flow.rendersAsked
    return auth('/render')
      .then(r => {
        if (asked < Flow.rendersShown) return
        Flow.rendersShown = asked
        Flow.renders = r
        m.redraw()
      })
      .catch(() => {})
      .then(() => LiveList.kick())
  },
}

// The rows the Deliver stage shows.
const VISIBLE_RENDERS = 12

// How far along each state is. A render only ever moves forward.
const PROGRESSION = { queued: 0, rendering: 1, rendered: 2, failed: 2 }

/** A render as the row should show it: the list's copy, brought up to date.
 *
 * Two sources answer independently -- the list, fetched now and then, and a
 * watched render's own status, asked every second or so -- and either can be
 * the more recent. Neither simply wins. A render only moves forward, so the
 * further-along state and the higher progress are the newer ones, whichever
 * source reported them.
 */
const current = r => {
  const live = RenderStatus.get(r._id)
  if (!live) return r
  const listed = renderState(r)
  const progress = [r.progress, live.progress].filter(p => typeof p === 'number')
  return {
    ...r,
    state: PROGRESSION[live.state] >= PROGRESSION[listed] ? live.state : listed,
    progress: progress.length ? Math.max(...progress) : null,
    error: live.error || r.error || null,
    filename: r.filename || live.filename || null,
    destination: r.destination || live.destination || null,
  }
}

/** Keeps the Deliver list moving while something on it has not finished.
 *
 * A render queued on this page is watched on its own (RenderStatus). This is
 * for the rest -- one queued in another tab, by the form, or before a reload --
 * which would otherwise show whatever state they were in when the stage
 * opened. One list request covers all of them, backing off while nothing
 * changes, and it stops when the stage closes or nothing is left to wait for.
 */
const LiveList = {
  active: false,
  timer: null,
  delay: 2000,
  seen: null,

  waiting: () =>
    Flow.renders
      .slice(0, VISIBLE_RENDERS)
      .filter(r => !isSettled(renderState(current(r))) && !RenderStatus.isWatching(r._id)),

  /** Schedule the next refresh if the stage is open and anything is unfinished. */
  kick: () => {
    if (!LiveList.active || LiveList.timer) return
    const waiting = LiveList.waiting()
    if (!waiting.length) return
    const seen = waiting.map(r => `${r._id}:${r.status}:${r.progress}`).join('|')
    LiveList.delay = seen === LiveList.seen ? Math.min(LiveList.delay * 1.6, 15000) : 2000
    LiveList.seen = seen
    LiveList.timer = setTimeout(() => {
      LiveList.timer = null
      if (LiveList.active && User.loggedIn) Flow.loadRenders()
    }, LiveList.delay)
  },

  start: () => {
    LiveList.active = true
    LiveList.seen = null
  },

  stop: () => {
    LiveList.active = false
    clearTimeout(LiveList.timer)
    LiveList.timer = null
  },
}

// A watched render that settles changes the list (a filename, a status), and
// a watcher that fell back to reading the list has the whole of it in hand.
RenderStatus.listen((type, id, payload) => {
  if (type === 'list' && Array.isArray(payload)) {
    // The newest list there is, so anything still in flight is older.
    Flow.rendersShown = ++Flow.rendersAsked
    Flow.renders = payload
  }
  if (type === 'settled') Flow.loadRenders()
})

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

/** A button that says when it is working.
 *
 * Every action on these panels talks to the server, and none of them said so:
 * the render button changed its own label and the deliver and generate buttons
 * changed nothing at all, so a slow request looked like a click that missed.
 * One component now carries the pending state, so a new async action cannot
 * quietly ship without an indicator.
 */
const Busy = () =>
  m('span.spinner', { 'aria-hidden': 'true' })

export const AsyncButton = () => ({
  view: vnode => {
    const { busy, label, busyLabel, ...attrs } = vnode.attrs
    return m(
      'button',
      {
        ...attrs,
        disabled: busy || attrs.disabled,
        'aria-busy': busy ? 'true' : 'false',
      },
      busy ? [Busy(), busyLabel || label] : label
    )
  },
})

/** An empty state that offers to fix itself.
 *
 * "No projects yet." and "No media on the server. `./al demo` downloads some."
 * were the two previous messages. Both accurate, neither useful: the first is
 * a dead end, and the second sends you to a shell to download four files over
 * the network before the editor will show you anything.
 *
 * Both are generated locally now, with ffmpeg's own test sources, so a first
 * run needs no downloads -- which also keeps a fresh install clear of the
 * third-party fetches the adoption record flags.
 */
/** The file's own name, without the directory it was served from. */
const basename = path => String(path).split('/').pop()

/** Put a clip on the end of the timeline, and say that it landed. */
const add = (clip, label, kind) => {
  const at = addClip(clip)

  // Say it landed, and where.
  //
  // The timeline is below the fold on a short window, so the only evidence of
  // a successful click could be off screen -- which is indistinguishable from
  // the click having done nothing, and was reported as exactly that.
  Flow.added = { name: label, at: at + 1, kind }
  clearTimeout(add.timer)
  add.timer = setTimeout(() => {
    Flow.added = null
    m.redraw()
  }, 4000)
}

const addMedia = name => add(videoClip(name), basename(name), 'media')

const addTemplate = template =>
  add(templateClip(template), `${template.name} template`, 'template')

const Generate = (message, label, action, busyKey) =>
  m('.stageempty', [
    m('p', message),
    m(AsyncButton, {
      class: 'generate',
      busy: Flow.generating === busyKey,
      label,
      busyLabel: 'Generating…',
      onclick: () => {
          Flow.generating = busyKey
          Flow.error = null
          action()
            .then(() => {
              Flow.generating = null
              Flow.load({ force: true })
            })
            .catch(() => {
              Flow.generating = null
              Flow.error = `Could not generate ${busyKey}`
              m.redraw()
            })
      },
    }),
  ])

/** Stage 1 -- pick the project, see what material is available to it.
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
const SourcePanel = {
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

      m('h3', `Material${Flow.videos.length ? ` (${Flow.videos.length})` : ''}`),
      Flow.videos.length
        ? [
            m(
              'p.stagehint',
              'Choose a clip to put it on the timeline.'
            ),
            Flow.added && Flow.added.kind === 'media'
              ? m('p.stageconfirm#media-added', [
                  m('i.material-icons', 'check'),
                  `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
                ])
              : null,
            m(
              'ul.medialist',
              Flow.videos.map(v =>
                m('li.mediaitem', [
                  // A button, not an `<li>` with text on it. This list was
                  // inert: it named the media on the server and offered no
                  // way to use any of it, so the only route from "I have
                  // footage" to "it is on the timeline" was to find the bin
                  // below and drag -- an affordance with no visible cue,
                  // unavailable from the keyboard, and on a different stage
                  // from the list that told you the footage existed.
                  m(
                    'button.mediachoice',
                    {
                      title: `Add ${basename(v)} to the timeline`,
                      onclick: () => addMedia(v),
                    },
                    [m('i.material-icons', 'add'), basename(v)]
                  ),
                ])
              )
            ),
          ]
        : Generate(
            'No media on the server.',
            'Generate demo media',
            () => auth('/demo/media', { method: 'POST' }),
            'media'
          ),

      // Templates are material too: a title card or a colour field is made,
      // not uploaded. They were reachable only by dragging from the bin,
      // which never worked -- the timeline refused drops from it, and the
      // drop handler threw on the template's shape when one was let through.
      Bin.templates.length
        ? [
            m('h3', `Templates (${Bin.templates.length})`),
            Flow.added && Flow.added.kind === 'template'
              ? m('p.stageconfirm#template-added', [
                  m('i.material-icons', 'check'),
                  `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
                ])
              : null,
            m(
              'ul.medialist.templatelist',
              Bin.templates.map(t =>
                m(
                  'li.mediaitem',
                  m(
                    'button.mediachoice.templatechoice',
                    {
                      'data-template': t.name,
                      title: t.description
                        ? `Add a ${t.name} clip — ${t.description.replace(/\*/g, '')}`
                        : `Add a ${t.name} clip to the timeline`,
                      onclick: () => addTemplate(t),
                    },
                    [
                      m('i.material-icons', 'add'),
                      t.name,
                      t.deprecated ? m('span.deprecated', 'deprecated') : null,
                    ]
                  )
                )
              )
            ),
          ]
        : null,
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

/** Stage 3 -- queue a render of what is on the timeline. */
const RenderPanel = {
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
  },
  onremove: () => LiveList.stop(),
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

/** The panel for the current stage. Edit has none -- it *is* the timeline. */
export const StagePanel = () => ({
  oninit: () => Flow.load(),
  // Same reason as the media bin: the session may not exist yet on the first
  // draw, and a panel that gave up then would stay empty for the whole visit.
  onupdate: () => Flow.load(),
  view: () => {
    const stage = Flow.stage()
    if (stage === 'source') return m(SourcePanel)
    if (stage === 'render') return m(RenderPanel)
    if (stage === 'deliver') return m(DeliverPanel)
    // Edit has no panel: it *is* the timeline, which is always mounted below.
    return null
  },
})
