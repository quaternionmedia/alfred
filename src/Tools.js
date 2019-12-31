import m from 'mithril'
import '../node_modules/material-design-icons/iconfont/material-icons.css'

export default class Tools {
  constructor() {

  }
  view(vnode) {
    return m('#tools.tools.', {}, [
      m('i.material-icons', 'play_arrow')
    ])
  }
}
