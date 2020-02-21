import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'

export default class TimelineTools {
  oncreate() {

  }
  view() {
    return m('#TTools', {}, [
      m('i.material-icons', {
        onclick: (vnode) => {

        }
      }, 'content_cut'),
      m('i.material-icons', {
        onclick: (vnode) => {

        }
      }, 'swap_horizontal'),
    ])
  }
}
