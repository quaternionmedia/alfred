import m from 'mithril'
import './styles/stages.scss'
import { auth } from './Login'
import { User } from './User'
import { OFFLINE_DELAY, RenderStatus, isSettled, renderState } from './RenderStatus'
import { Health } from './Health'
import { addClip, mediaClip, templateClip } from './Clips'
import { Library } from './Library'
import { expiresAt } from './Signed'

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
 *
 * This module is the flow's state and its rail. What each stage shows is a
 * panel (panels/), and where the panels sit is the layout's (layout/): a
 * workspace of them on a wide screen, one stage at a time on a phone.
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
    for (const follower of Flow.followers) follower(id)
  },

  // Told each time `go` is asked for a stage -- the one already open too,
  // which changes nothing in the address. The desktop workspace brings the
  // stage's panels forward (layout/workspace.js), since one may have been
  // closed or put behind another since the stage was last chosen.
  followers: [],

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
    // /users/me answers -- and a stage panel's `oninit` runs before that. Loading
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
    // The media library is the page's own (Library.js), shared with the bin.
    Library.load({ force: Boolean(opts && opts.force) })
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
export const VISIBLE_RENDERS = 12

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
export const current = r => {
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
    // Whichever signed link runs out later: both were issued by the server,
    // at different moments.
    download_url: laterLink(live.download_url, r.download_url),
  }
}

const laterLink = (a, b) => {
  if (!a || !b) return a || b || null
  return (expiresAt(a) || 0) >= (expiresAt(b) || 0) ? a : b
}

/** Keeps the Deliver list moving while something on it has not finished.
 *
 * A render queued on this page is watched on its own (RenderStatus). This is
 * for the rest -- one queued in another tab, by the form, or before a reload --
 * which would otherwise show whatever state they were in when the stage
 * opened. One list request covers all of them, backing off while nothing
 * changes, and it stops when the stage closes or nothing is left to wait for.
 */
export const LiveList = {
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
    // Nothing queued can move while no renderer runs, so the list is asked
    // for rarely then -- and quickly again once one starts (see below).
    const stuck =
      Health.rendererDown() && waiting.every(r => renderState(current(r)) === 'queued')
    LiveList.delay = stuck
      ? OFFLINE_DELAY
      : seen === LiveList.seen
        ? Math.min(LiveList.delay * 1.6, 15000)
        : 2000
    LiveList.seen = seen
    LiveList.timer = setTimeout(() => {
      LiveList.timer = null
      if (LiveList.active && User.loggedIn) Flow.loadRenders()
    }, LiveList.delay)
  },

  /** Refresh soon, at the quick pace again. */
  hurry: () => {
    clearTimeout(LiveList.timer)
    LiveList.timer = null
    LiveList.seen = null
    LiveList.kick()
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

// A renderer has started: whatever was queued can move now.
Health.listen(down => {
  if (!down) LiveList.hurry()
})

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

export const Empty = message => m('p.stageempty', message)

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
export const basename = path => String(path).split('/').pop()

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

export const addMedia = name => add(mediaClip(name), basename(name), 'media')

export const addTemplate = template =>
  add(templateClip(template), `${template.name} template`, 'template')

export const Generate = (message, label, action, busyKey) =>
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

/**
 * A stage's panel, wrapped the way the stage panel wrapped each one.
 *
 * The four stages were one component that loaded the flow's lists when it
 * was drawn and again on later draws -- a restored session answers after the
 * first draw, and a panel that gave up then would stay empty for the visit.
 * The stages are panels now, placed by the layout (layout/), so each carries
 * that loading itself and assumes nothing about what is around it.
 */
export const FlowPanel = component => ({
  oninit: () => Flow.load(),
  onupdate: () => Flow.load(),
  view: vnode => m(component, vnode.attrs),
})
