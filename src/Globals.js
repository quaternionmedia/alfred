
var Stream = require("mithril/stream")

exports.state = {
  paused: Stream(true),
  scale: Stream(10),
}
