import m from 'mithril'
import '../node_modules/material-design-icons/iconfont/material-icons.css'
import Monitor from './Monitor'
import Video from './Video'
var state = require("./Globals").state

export default class Tools {
  
  view(vnode) {
    return m('#tools.tools.', {}, [
      m('i.material-icons', {
        onclick: Monitor.play,
      }, Video.paused ? 'pause' : 'play_arrow')
    ])
  }
}
