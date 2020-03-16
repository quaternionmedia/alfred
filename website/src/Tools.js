import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import Monitor from './Monitor'
import { Video, Edl } from './Video'
var state = require("./Globals").state
import { message, success, defaults } from 'alertifyjs'

export function downloadFile(url) {
  var a = document.createElement("a")
  document.body.appendChild(a)
  a.style = "display: none"
  a.href = url
  a.click()
  document.body.removeChild(a)
}
export default class Tools {
  view(vnode) {
    return m('#tools.tools.', {}, [

      m('i.material-icons', {
        title: 'start',
        onclick: (vnode) => {Monitor.seekEdl(0)}
      }, 'first_page'),
      m('i.material-icons', {
        title: 'back 5s',
        onclick: (vnode) => {
          Monitor.seekEdl(Edl.time - 5 || 0)}
        }, 'fast_rewind'),
        m('i.material-icons', {
          title: 'pause',
          onclick: Monitor.play,
        }, Video.paused ? 'play_arrow': 'pause' ),
        m('i.material-icons', {
          title: 'forward 5s',
          onclick: (vnode) => {
            Monitor.seekEdl(Math.min(Edl.time + 5, Edl.duration()))}
          }, 'fast_forward'),
          m('i.material-icons', {
            title: 'end',
            onclick: (vnode) => {Monitor.seekEdl(Edl.duration())}
          }, 'last_page'),
          m('i.material-icons', {
            title: 'slower',
            onclick: (vnode) => {Monitor.slower()}
          }, 'slow_motion_video'),
          m('i', {
            title: 'reset speed',
            onclick: (vnode) => {Monitor.resetSpeed()}
          }, Video.speed + 'x'),
          m('i.material-icons', {
            title: 'faster',
            onclick: (vnode) => {Monitor.faster()}
          }, 'speed'),
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
                message(`saved! ${e['filename']}`, 3)
              })
            }
          }, 'save'),
          m('i.material-icons', {
            title: 'render',
            onclick: (vnode) => {
              // console.log('export')
              message(`Added ${m.route.param("edl")} to render queue`, 5)
              m.request({
                url: '/render',
                params: { edl: m.route.param('edl') },
              }).then(e => {
                console.log('got result', e)
                m.route.set('/renders')
                // success(`Successfully rendered ${m.route.param('edl')}`)
                // downloadFile('/download?filename=' + m.route.param('edl') + '.mp4')
              }
            )
          }
        }, 'file_download'),
      ]
    )
  }
}
