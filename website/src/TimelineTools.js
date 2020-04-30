import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
var state = require("./Globals").state

export default class TimelineTools {
  oncreate() {

  }
  view() {
    let t = document.getElementById('timeline')
    return m('#TTools.tools', {}, [
      m('i', {
        title: 'time selector',
          onclick: (vnode) => {
            t.style.cursor = 'text'
            state.tool('time')
          }
      }, '|'),
      m('i', {
        title: 'trim',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('trim')
        }
      }, '[ ]'),
      m('i.material-icons', {
        title: 'cut',
        onclick: (vnode) => {
          t.style.cursor = 'url(content-cut.svg), auto'
          state.tool('cut')
        }
      }, 'content_cut'),
      m('i.material-icons', {
        title: 'move',
        onclick: (vnode) => {
          t.style.cursor = 'url(swap-horizontal.svg), -webkit-grab'
          state.tool('move')
        }
      }, 'swap_horizontal'),
      m('i.material-icons', {
        title: 'slip',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('slip')
        }
      }, 'swap_calls'),
      m('i.material-icons', {
        title: 'slide',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('slide')
        }
      }, 'sync_alt'),
      m('i.material-icons', {
        title: 'dual roller',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('dual roller')
        }
      }, 'compare_arrows'),
    ])
  }
}
