import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'

export default class TimelineTools {
  oncreate() {

  }
  view() {
    let t = document.getElementById('timeline')
    return m('#TTools.tools', {}, [
      m('i', {
          onclick: (vnode) => {
            t.style.cursor = 'text'
          }
      }, '|'),
      m('i.material-icons', {
        onclick: (vnode) => {
          console.log('changing timeline tools', t)
          t.style.cursor = 'url(content-cut.svg), auto'
        }
      }, 'content_cut'),
      m('i.material-icons', {
        onclick: (vnode) => {
          t.style.cursor = 'url(swap-horizontal.svg), auto'

        }
      }, 'swap_horizontal'),
    ])
  }
}
