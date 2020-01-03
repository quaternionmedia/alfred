import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import Monitor from './Monitor'
import { Video } from './Video'
var state = require("./Globals").state

export default class Tools {
  oncreate(vnode) {
    document.addEventListener('keydown', (e) => {
      switch (e.which) {
        case 37:
          e.preventDefault()
          Monitor.seek(Video.time - 5)
          break
        case 39:
          e.preventDefault()
          Monitor.seek(Video.time + 5)
          break

      }
    })
  }

  view(vnode) {
    return m('#tools.tools.', {}, [

      m('i.material-icons', {
        onclick: (vnode) => {Monitor.seek(0)}
      }, 'first_page'),
      m('i.material-icons', {
        onclick: (vnode) => {
          Monitor.seek(Video.time - 5 || 0)}
      }, 'fast_rewind'),
      m('i.material-icons', {
        onclick: Monitor.play,
      }, Video.paused ? 'play_arrow': 'pause' ),
      m('i.material-icons', {
        onclick: (vnode) => {
          Monitor.seek(Math.min(Video.time + 5, Video.duration))}
      }, 'fast_forward'),
      m('i.material-icons', {
        onclick: (vnode) => {Monitor.seek(Video.duration)}
      }, 'last_page'),
      m('i.material-icons', {
        onclick: (vnode) => {Monitor.slower()}
      }, 'slow_motion_video'),

      m('i', {
        onclick: (vnode) => {Monitor.resetSpeed()}
      }, Video.speed + 'x'),
      m('i.material-icons', {
        onclick: (vnode) => {Monitor.faster()}
      }, 'speed'),
    ])
  }
}
