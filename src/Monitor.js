import m from 'mithril'
var state = require("./Globals").state
import { Video, Edl } from './Video'

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
  seekEdl: (t) => {
    let c =0
    let d = 0
    while (d + Edl.edl[c][3] <= t && c < Edl.edl.length - 1) {
      d += Edl.edl[c++][3]
    }
    Edl.current = c
    let clip = Edl.edl[c]
    let clipTime =  parseFloat(t - d + clip[1]).toFixed(2)
    console.log('seeking edl', c, d, t, clipTime)
    if (Video.filename != clip[0]) {
      module.exports.load(clip[0])
    }
    module.exports.seek(clipTime)
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
  stop: () => {
    Mon.dom.pause()
    Video.paused = true
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
  load: (f) => {
    Mon.dom.src = f
    Video.filename = f
  },
  oncreate: (vnode) => {
    // Video.filename = Edl.edl[0][0]
    vnode.dom.addEventListener('durationchange', (e) => {
      Video.duration = vnode.dom.duration
      // console.log('duration change', Video)
      // m.redraw()
    })
    Video.duration = vnode.duration
    // console.log('monitor created', Video)
    Mon.dom = vnode.dom
    document.addEventListener('keydown', e => {
      switch (e.code) {
        case 'Space':
          e.preventDefault()
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
        case 'ArrowLeft':
          e.preventDefault()
          module.exports.seekEdl(Edl.time - 5 || 0)
          break
        case 'ArrowRight':
          e.preventDefault()
          module.exports.seekEdl(Math.min(Edl.time + 5, Edl.duration()))
          break

      }
    })

    vnode.dom.addEventListener('timeupdate', (e) => {
      Video.time = e.target.currentTime
      Edl.time = Video.time - Edl.edl[Edl.current][1] + Edl.durations(Edl.edl.slice(0, Edl.current))
      // if (Edl.edl[Edl.current]) {
      console.log('timeupdate', e, Video, Edl)
      // , Edl.edl[Edl.current][2] - Video.time)
      // check to see if we need to make an edit in the monitor
      // if the current video time is beyond the current clip outpoint:
      if (Video.time > Edl.edl[Edl.current][2]) {
        // and if there's another clip to edit to:
        if (Edl.current < Edl.edl.length - 1) {
          // we need to change the video somehow.
          console.log('editing!', Video, Edl )
          // if the next video is different than the current video:
          if (Video.filename != Edl.edl[++Edl.current][0]) {
            // we need to switch videos
            console.log('loading', Video, Edl.edl[Edl.current])
            module.exports.load(Edl.edl[Edl.current][0])
          }
          // perform the edit!
          if (!Video.paused) {
            module.exports.seek(parseFloat(Edl.edl[Edl.current][1]))
          }
        } else {
          // this is the last clip in the edl.
          console.log('End of edl. stopping')
          // since Video.time > current outpoint
          module.exports.seek(parseFloat(Edl.edl[Edl.current][2]))
          module.exports.stop()
        }
      }
      // }
      m.redraw()
    })
    Mon.dom.addEventListener('loadeddata', (event) => {
      if (!Video.paused && Mon.dom.paused) {
        console.log('fixed paused!')
        Mon.dom.play()
      }
      if (Video.time < Edl.edl[Edl.current][1]) {
        console.log('jumping to inpoint')
        module.exports.seek(Edl.edl[Edl.current][1])
      }
    })
  },
  onbeforeupdate: (vnode, old) => {
    // prevent component from updating on redraw
    return false
  },
  view: (vnode) => {
    return m('video#monitor.monitor', {
      src: Video.filename,
      controls: true,
      preload: true,
      volume: Video.volume,
      // currentTime: Video.time,
    })
  }
}
