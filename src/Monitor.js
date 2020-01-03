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
  faster: () => {
    console.log('playbackRate changed', Video)
    if (Video.speed < -.25) {
      Video.speed = (parseFloat(Video.speed) / 2).toFixed(2)
    } else if (Video.speed < 1) {
      Video.speed = parseFloat(Video.speed) + .25
    } else if (Video.speed < 16){
      Video.speed = parseFloat(Video.speed) * 2
    }
    if (Video.speed == .25) {
      Mon.dom.play()
    } else {
      Mon.dom.playbackRate = Video.speed
    }
  },
  slower: () => {
    if (Video.speed > 1) {
      Video.speed = (Video.speed / 2).toFixed()
    } else if (Video.speed > 0) {
      Video.speed -= .25
    } else {
      // Video.speed = Video.speed * 2
    }
    if (Video.speed == 0) {
      Mon.dom.pause()
    } else {
      Mon.dom.playbackRate = Video.speed
    }
  },
  resetSpeed: () => {
    Video.speed = 1
    Mon.dom.playbackRate = Video.speed
    m.redraw()
  },
  oncreate: (vnode) => {
    Video.filename = vnode.attrs.src
    vnode.dom.addEventListener('durationchange', (e) => {
      Video.duration = vnode.dom.duration
      // console.log('duration change', Video)
      // m.redraw()
    })
    Video.duration = vnode.duration
    // console.log('monitor created', Video)
    Mon.dom = vnode.dom
    document.addEventListener('keyup', e => {
      switch (e.code) {
        case 'Space':
          module.exports.play()
          // console.log('space', Video, vnode)
          m.redraw()
          break
          case 'Equal':
          module.exports.faster()
          break
          case 'Minus':
          module.exports.slower()
          break
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
      // console.log('timeupdate', e, Slider)
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
