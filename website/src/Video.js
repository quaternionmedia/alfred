import m from 'mithril'

var Video = {
  paused: true,
  filename: "",
  time: 0,
  duration: 0,
  volume: .1,
  speed: 1,
}

var Edl = {
  edl: [],
  current: 0,
  time: 0,
  duration: () => {
    return Edl.edl.reduce((a, b) => a + b[3], 0)
  },
  durations: (e) => {
    let d = e.map(clip => clip[3])
    return d.reduce((a, b) => a + b, 0)
  },
}

module.exports = {Video, Edl}