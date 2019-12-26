import m from 'mithril'
var state = require("./Globals").state

export default class Monitor {
  constructor(vnode) {
    this.src = vnode.attrs.src
  }
  oncreate(vnode) {
    this.dom = vnode.dom
    document.addEventListener('keyup', event => {
  if (event.code === 'Space') {
    console.log('space', vnode)
    if (vnode.dom.paused) {
      vnode.dom.play()
    } else {
      vnode.dom.pause()
    }
    state.paused(vnode.dom.paused)
  }
})
  }
  view(vnode) {
    return m('video#monitor.monitor', {
        src: this.src,
        controls: true,
        preload: true,
      })
  }
}
