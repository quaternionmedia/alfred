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
          onclick: (vnode) => {
            t.style.cursor = 'text'
            state.tool('time')
          }
      }, '|'),
      m('i', {
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('trim')
        }
      }, '[ ]'),
      m('i.material-icons', {
        onclick: (vnode) => {
          console.log('changing timeline tools', t)
          t.style.cursor = 'url(content-cut.svg), auto'
          state.tool('cut')
        }
      }, 'content_cut'),
      m('i.material-icons', {
        onclick: (vnode) => {
          t.style.cursor = 'url(swap-horizontal.svg), auto'

          state.tool('move')
        }
      }, 'swap_horizontal'),
    ])
  }
}
