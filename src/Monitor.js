import m from 'mithril'
var state = require("./Globals").state

export default class Monitor {
  constructor(vnode) {
    this.src = vnode.attrs.src
  }
  view(vnode) {
    return m('#monitor.monitor', {}, [
      m('video', {
        src: this.src,
        controls: true,
        preload: true,
      })
    ])
  }
}
