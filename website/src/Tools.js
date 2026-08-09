import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import { Player } from './Player'
import { Video, Edl } from './Video'
var state = require("./Globals").state
import { message, success, defaults } from 'alertifyjs'
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
  return {
    view: vnode => {
      return m('.tools.toolbar', {}, [
          m('i.material-icons', {
            title: 'save',
            onclick: vnode => {
              m.request({
                url: '/edl',
                method: 'post',
                params: {
                  filename: m.route.param('edl')
                },
                body: {'edl': Edl.edl}
              }).then(e => {
                let resp = JSON.parse(e)
                console.log('sucessfully saved', resp)
                message(`saved! ${resp.filename}`, 3)
              })
            }
          }, 'save'),
          m('i.material-icons', {
            title: 'render',
            onclick: (vnode) => {
              // console.log('export')
              m.request({
                url: '/render',
                method: 'post',
                params: {
                  project: m.route.param('project'),
                  width: state.width(),
                  height: state.height(),
                },
                body: { edl: Edl.edl },
              }).then(e => {
                console.log('got result', e)
                message(`Added ${m.route.param("project")} to render queue`, 5)
                m.route.set('/renders')
              }
            )
          }
        }, 'file_upload'),
      ])
    }
  }
}
