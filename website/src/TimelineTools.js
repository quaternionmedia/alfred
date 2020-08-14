import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
var state = require("./Globals").state

export default class TimelineTools {
  oncreate() {

  }
  view() {
    let t = document.getElementById('timeline')
    return m('span#TTools.tools.toolcol', {}, [
      m('i.custom', {
        title: 'time selector',
          onclick: (vnode) => {
            t.style.cursor = 'text'
            state.tool('time')
          },
          style: {
            'background-color': state.tool() == 'time' ? '#393939' : 'transparent'
          }
      }, '|'),
      m('i.material-icons', {
        title: 'trim',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('trim')
        },
        style: {
          'background-color': state.tool() == 'trim' ? '#393939' : 'transparent'
        }
      }, 'code'),
      m('i.material-icons', {
        title: 'move',
        onclick: (vnode) => {
          t.style.cursor = 'url(swap-horizontal.svg), -webkit-grab'
          state.tool('move')
        },
        style: {
          'background-color': state.tool() == 'move' ? '#393939' : 'transparent'
        }
      }, 'swap_horizontal'),
      m('i.material-icons', {
        title: 'cut',
        onclick: (vnode) => {
          t.style.cursor = 'url(content-cut.svg), auto'
          state.tool('cut')
        },
        style: {
          'background-color': state.tool() == 'cut' ? '#393939' : 'transparent'
        }
      }, 'content_cut'),
      m('i.material-icons', {
        title: 'slip',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('slip')
        },
        style: {
          'background-color': state.tool() == 'slip' ? '#393939' : 'transparent'
        }
      }, 'swap_calls'),
      m('i.material-icons', {
        title: 'slide',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('slide')
        },
        style: {
          'background-color': state.tool() == 'slide' ? '#393939' : 'transparent'
        }
      }, 'sync_alt'),
      m('i.material-icons', {
        title: 'dual roller',
        onclick: (vnode) => {
          t.style.cursor = 'ew-resize'
          state.tool('dual roller')
        },
        style: {
          'background-color': state.tool() == 'dual roller' ? '#393939' : 'transparent'
        }
      }, 'compare_arrows'),
    ])
  }
}
