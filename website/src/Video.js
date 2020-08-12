import m from 'mithril'
var Stream = require("mithril/stream")

export var Video = {
  clip: null,
  paused: true,
  filename: "",
  time: Stream(0),
  duration: 0,
  volume: .1,
  speed: 1,
}

export var Edl = {
  edl: [],
  current: 0,
  time: 0,
  duration: () => {
    if (Edl.edl.length > 0) {
      return Edl.edl.reduce((a, b) => a + (b ? b['duration'] : 0), 0)
    } else {
      return 0
    }
  },
  durations: (e) => {
    let d = e.map(clip => clip['duration'])
    return d.reduce((a, b) => a + b, 0)
  },
  update: () => {
    let edl = Edl.edl
    Edl.edl = []
    m.redraw.sync()
    Edl.edl = edl
    m.redraw.sync()
    console.log('edl updated', Edl.edl)
  },
  which: (t) => {
    let c = 0
    let i = 0
    while (c + Edl.edl[i].duration < t) {
      c += Edl.edl[i].duration
      i++
    }
    return i
  },
  jump: (t) => {
    let n = Edl.which(t)
    if (n != Edl.current) {
      Video.clip = Edl.edl[n]
      Edl.current = n
    }
    Edl.time = t
    Video.time(t - Edl.durations(Edl.edl.slice(0, n)))
    m.redraw.sync()
  },
  play: play
}

function updateTime(e) {
  let t = e.target.currentTime
  let p = Edl.durations(Edl.edl.slice(0,Edl.current))
  let d = Edl.edl[Edl.current].duration
  console.log('timeupdate', Edl.current, p, t)
  if (t >= d) {
    // switch to next clip
    Edl.jump(t + d)
  } else {
    // update playback time
    Video.time(t)
    Edl.time = t + p
  }
  m.redraw()
}
function play() {
  let d = document.getElementById('preview')
  if (Video.paused) {
    d.play()
    Video.paused = false
    d.addEventListener('timeupdate', updateTime)
  } else {
    d.pause()
    Video.paused = true
    d.removeEventListener('timeupdate', updateTime)
  }
  m.redraw()
}

export function array_move(arr, old_index, new_index) {
  let element = arr[old_index];
  arr.splice(old_index, 1);
  arr.splice(new_index, 0, element);
  return arr
};
