
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
    if (state.aspectWidth() > state.aspectHeight()) {
      return parseInt(state.resolution()*state.aspectWidth()/state.aspectHeight())
    } else {
      return parseInt(state.resolution())
    }
  },
  height: () => {
    if (state.aspectWidth() > state.aspectHeight()) {
      return parseInt(state.resolution())
    } else {
      return parseInt(state.resolution()*state.aspectWidth()/state.aspectHeight())
    }
  },
  resolution: Stream(1080),
  aspectWidth: Stream(16),
  aspectHeight: Stream(9),
}
