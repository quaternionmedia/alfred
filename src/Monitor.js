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
    vnode.dom.addEventListener('durationchange', (e) => {
      Video.duration = vnode.dom.duration
      console.log('duration change', Video)
      // m.redraw()
    })
    Video.duration = vnode.duration
    console.log('monitor created', Video)
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
      // state.time(e.target.currentTime)
      Video.time = e.target.currentTime
      console.log('timeupdate', e, Slider)
      m.redraw()
      // Slider.updateValue(e.target.currentTime)
    })
  },
  onbeforeupdate: (vnode, old) => {
    // prevent component from updating on redraw
    return false
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
