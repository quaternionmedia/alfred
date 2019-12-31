import m from 'mithril'
var state = require("./Globals").state
// import Slider from './Slider'
var Slider = require("./Slider")
// import Slider from './Slider'
import Video from './Video'

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
  play: () => {
    if (Video.paused) {
      Mon.dom.play()
      Video.paused = false
    } else {
      Mon.dom.pause()
      Video.paused = true
    }
  },
  oncreate: (vnode) => {
    Video.filename = vnode.attrs.src
    Mon.dom = vnode.dom
    document.addEventListener('keyup', e => {
      if (e.code === 'Space') {
        // vnode.dom.paused ? vnode.dom.play() : vnode.dom.pause()
        // state.paused(vnode.dom.paused)
        // module.exports.paused = vnode.dom.paused
        // Video.paused = vnode.dom.paused
        module.exports.play()
        // console.log('space', Video, vnode)
        m.redraw()
      }
    })
    document.addEventListener('keydown', e => {
      if (e.code === 'Space') {
        e.preventDefault()
      }
    })
    vnode.dom.addEventListener('timeupdate', (e) => {
      state.time(e.target.currentTime)
      // console.log('timeupdate', e, Slider)
      // Slider.updateValue(e.target.currentTime)
    })
  },
  view: (vnode) => {
    return m('video#monitor.monitor', {
        src: vnode.attrs.src,
        controls: true,
        preload: true,
        volume: Video.volume,
        currentTime: Video.time,
      })
  }
}
