import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import { Player } from './Player'
import { Video, Edl } from './Video'
import { auth } from './Login'
var state = require("./Globals").state
import { message, success, error, defaults } from 'alertifyjs'
import { Resolution, Aspect } from './Resolution'

export function downloadFile(url) {
  var a = document.createElement("a")
  document.body.appendChild(a)
  a.style = "display: none"
  a.href = url
  a.click()
  document.body.removeChild(a)
}
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

export function ProjectTools() {
  let saving = false
  let rendering = false

  return {
    view: () => {
      const project = m.route.param('project')
      const clips = Edl.edl.length

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
              // `/project/{id}/timeline`, and with a token.
              //
              // This posted to `/edl` with a bare `m.request` -- no route of
              // that name has ever existed on this server, and no
              // Authorization header would have been sent if it had. So the
              // save button had never once saved anything, and said nothing
              // when it failed: the response was parsed inside a `.then` with
              // no `.catch`, so the rejection went nowhere.
              auth(`/project/${project}/timeline`, {
                method: 'PUT',
                body: { clips: Edl.edl },
              })
                .then(() => {
                  saving = false
                  success(`Saved ${Edl.edl.length} clips to the project`)
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
            title: cannotRender || 'Render this timeline',
            class: cannotRender ? 'disabled' : '',
            onclick: () => {
              if (cannotRender || rendering) return
              rendering = true
              auth('/render', {
                method: 'POST',
                params: {
                  project,
                  width: state.width(),
                  height: state.height(),
                },
                body: { edl: { clips: Edl.edl } },
              })
                .then(() => {
                  rendering = false
                  message('Added to the render queue', 5)
                  // Into the flow, not to the retired `/renders` route.
                  m.route.set('/', { stage: 'deliver', project })
                })
                .catch(() => {
                  rendering = false
                  error('Could not queue the render', 4)
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
