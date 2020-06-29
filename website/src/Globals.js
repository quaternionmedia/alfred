
var Stream = require("mithril/stream")

export var state = {
  edl: Stream([]),
  paused: Stream(true),
  scale: Stream(50),
  volume: Stream(.1),
  time: Stream(0),
  duration: Stream(0),
  tool: Stream('time'),
  width: () => {
    if (state.aspectWidth() >= state.aspectHeight()) {
      let w = parseInt(state.resolution()/state.aspectWidth()*state.aspectHeight())
      if (w % 2 != 0) {
        w -= 1
      }
      return w
    } else {
        return state.resolution()
    }
  },
  height: () => {
    if (state.aspectWidth() >= state.aspectHeight()) {
      return state.resolution()
    } else {
      let h = parseInt(state.resolution()/state.aspectHeight()*state.aspectWidth())
      if (h % 2 != 0) {
        h -= 1
      }
      return h
    }
  },
  resolution: Stream(1080),
  aspectWidth: Stream(16),
  aspectHeight: Stream(9),
}
