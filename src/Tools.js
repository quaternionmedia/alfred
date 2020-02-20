import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import Monitor from './Monitor'
import { Video, Edl } from './Video'
var state = require("./Globals").state

export default class Tools {
  oncreate(vnode) {
    document.addEventListener('keydown', (e) => {
      switch (e.which) {
        case 37:
          e.preventDefault()
          Monitor.seekEdl(Edl.time - 5)
          break
        case 39:
          e.preventDefault()
          Monitor.seekEdl(Edl.time + 5)
          break

      }
    })
  }

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
        title: 'render',
        onclick: (vnode) => {
          console.log('export');
          m.request({
            url: '/render',
            params: { edl: m.route.param('edl') },
          }).then(e => {
            console.log('got result', e);
            // m.request('/renders/' + e);
          });
        }
      }, 'save_alt')
    ])
  }
}
