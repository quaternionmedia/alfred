import m from 'mithril'
var state = require("./Globals").state

var Mon = {
  dom: null,
}

module.exports = {
  dom: null,
  seek: (t) => {
    if (Mon.dom) {
      Mon.dom.currentTime = t
    }
  },
  oncreate: (vnode) => {
    Mon.dom = vnode.dom
    document.addEventListener('keyup', e => {
      if (e.code === 'Space') {
        vnode.dom.paused ? vnode.dom.play() : vnode.dom.pause()
        state.paused(vnode.dom.paused)
      }
    })
    document.addEventListener('keydown', e => {
      if (e.code === 'Space') {
        e.preventDefault()
      }
    })
    vnode.dom.addEventListener('timeupdate', (e) => {
      state.time(e.target.currentTime)
    })
  },
  view: (vnode) => {
    return m('video#monitor.monitor', {
        src: vnode.attrs.src,
        controls: true,
        preload: true,
        volume: state.volume(),
        currentTime: state.time(),
      })
  }
}
