import m from 'mithril'
import { Player } from './Player'
import { Video, Edl } from './Video'
import { auth } from './Login'
import { message, success, error, defaults } from 'alertifyjs'
import { Resolution, Aspect } from './Resolution'
import { queueRender, renderSize, timelineEdl, timelineRender } from './RenderRequest'
import { requestProblem } from './Problem'
import { Flow } from './Stages'
import { Draft } from './Draft'

// `downloadFile(url)` lived here and was never called: an anchor pointed at a
// protected URL cannot carry the session's Authorization header, so it could
// not have downloaded a render if anything had used it. Download.js fetches
// with the session and hands the browser the bytes.

export function PlaybackTools() {
  return {
    view(vnode) {
      // `Player`, not `Monitor`. Every one of these reached through a module
      // that was never mounted, so its element reference was null and the
      // handler threw on the first click -- silently, since nothing catches a
      // handler's exception. The play button in particular did nothing at all,
      // which is the complaint that produced this change.
      const empty = !Player.playable()
      return m('#PlaybackTools.tools.toolbar', {}, [
        m(
          'i.material-icons',
          {
            title: 'start',
            class: empty ? 'disabled' : '',
            onclick: () => Player.seek(0),
          },
          'first_page'
        ),
        m(
          'i.material-icons',
          {
            title: 'back 5s',
            class: empty ? 'disabled' : '',
            onclick: () => Player.seek(Math.max(Edl.time - 5, 0)),
          },
          'fast_rewind'
        ),
        m(
          'i.material-icons#playpause',
          {
            // The title tracks the action, so a screen reader and a tooltip
            // agree with the icon. It read "pause" in both states.
            title: empty
              ? 'nothing on the timeline to play'
              : Video.paused
                ? 'play'
                : 'pause',
            class: empty ? 'disabled' : '',
            onclick: () => Player.toggle(),
          },
          Video.paused ? 'play_arrow' : 'pause'
        ),
        m(
          'i.material-icons',
          {
            title: 'forward 5s',
            class: empty ? 'disabled' : '',
            onclick: () => Player.seek(Math.min(Edl.time + 5, Edl.duration())),
          },
          'fast_forward'
        ),
        m(
          'i.material-icons',
          {
            title: 'end',
            class: empty ? 'disabled' : '',
            onclick: () => Player.seek(Edl.duration()),
          },
          'last_page'
        ),
      ])
    },
  }
}

export function SpeedTools() {
  return {
    view: vnode => {
      return m('.tools.toolbar', {}, [
        m(
          'i.material-icons',
          { title: 'slower', onclick: () => Player.slower() },
          'slow_motion_video'
        ),
        m(
          'i.custom#speed',
          { title: 'reset speed', onclick: () => Player.resetSpeed() },
          Video.speed + 'x'
        ),
        m('i.material-icons', { title: 'faster', onclick: () => Player.faster() }, 'speed'),
      ])
    },
  }
}

/**
 * Save the timeline on screen to `project`; resolves to the clip count.
 * Used by the toolbar's Save and the Transcript panel's.
 *
 * `/project/{id}/timeline`, and with a token. This posted to `/edl` with a
 * bare `m.request` -- no route of that name has ever existed on this server,
 * and no Authorization header would have been sent if it had. So the save
 * button had never once saved anything, and said nothing when it failed: the
 * response was parsed inside a `.then` with no `.catch`, so the rejection
 * went nowhere.
 *
 * The timeline as a render receives it (contract M4): every clip placed by an
 * explicit start, its fades explicit, its window in step with its length --
 * built by the same function, so a saved project renders as this editor
 * renders it, from here or from anything else that reads `project.edl`. This
 * sent the raw clips, view bookkeeping (`i`) included, with no starts:
 * rendered as saved, they stacked at second 0.
 */
export function saveTimeline(project) {
  const edl = timelineEdl(Edl.edl)
  return auth(`/project/${project}/timeline`, { method: 'PUT', body: edl }).then(updated => {
    // The project list shows clip counts and lengths.
    if (updated && updated._id) {
      Flow.projects = Flow.projects.map(p => (p._id === updated._id ? updated : p))
    }
    // What was saved is no longer a draft (Draft.js).
    Draft.saved(project, edl.clips)
    return edl.clips.length
  })
}

export function ProjectTools() {
  let saving = false
  let rendering = false

  return {
    view: () => {
      const project = m.route.param('project')
      const clips = Edl.edl.length
      // The size the Render stage would offer for this project, so the two
      // ways of rendering agree -- and the title says what it will be, since
      // this button has no fields of its own to show it.
      const size = renderSize(Flow.project())

      // Why each action is unavailable, or null when it is available. Saying
      // which of two preconditions is missing is the difference between a
      // control a person can act on and one that is merely inert.
      const cannotSave = !project
        ? 'Select a project before saving a timeline to it'
        : !clips
          ? 'Nothing on the timeline to save'
          : null
      const cannotRender = !project
        ? 'Select a project before rendering'
        : !clips
          ? 'Nothing on the timeline to render'
          : null

      return m('.tools.toolbar', {}, [
        m(
          'i.material-icons#save-timeline',
          {
            title: cannotSave || 'Save this timeline to the project',
            class: cannotSave ? 'disabled' : '',
            onclick: () => {
              if (cannotSave || saving) return
              saving = true
              saveTimeline(project)
                .then(saved => {
                  saving = false
                  success(`Saved ${saved} clips to the project`)
                  m.redraw()
                })
                .catch(() => {
                  saving = false
                  error('Could not save the timeline', 4)
                  m.redraw()
                })
            },
          },
          saving ? 'hourglass_top' : 'save'
        ),
        m(
          'i.material-icons#render-timeline',
          {
            title: cannotRender || `Render this timeline at ${size.width}×${size.height}`,
            class: cannotRender ? 'disabled' : '',
            onclick: () => {
              if (cannotRender || rendering) return
              rendering = true
              // The Render stage's request, built by the same function.
              //
              // This sent the project and size as query parameters, which
              // `POST /render` never reads -- it takes the body -- so every
              // render from this button came out at the 1920x1080 default with
              // no project, and its clips without starts, stacked at second 0.
              queueRender(
                timelineRender({
                  project: Flow.project(),
                  projectId: project,
                  ...size,
                })
              )
                .then(() => {
                  rendering = false
                  message('Added to the render queue', 5)
                  // Already on Deliver means no remount to reload the list.
                  Flow.loadRenders()
                  // Into the flow, not to the retired `/renders` route.
                  m.route.set('/', { stage: 'deliver', project })
                })
                .catch(e => {
                  rendering = false
                  const why = requestProblem(e)
                  error(
                    why ? `Could not queue the render: ${why}` : 'Could not queue the render',
                    6
                  )
                  m.redraw()
                })
            },
          },
          rendering ? 'hourglass_top' : 'file_upload'
        ),
      ])
    },
  }
}
