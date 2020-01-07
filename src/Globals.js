
var Stream = require("mithril/stream")

exports.state = {
  edl: Stream([]),
  paused: Stream(true),
  scale: Stream(1),
  volume: Stream(.1),
  time: Stream(0),
  duration: Stream(0),
}
