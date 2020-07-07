import m from 'mithril'
var Stream = require("mithril/stream")

export var VideoForm = {
  project: Stream(''),
  name: Stream(''),
  logo: Stream(''), //AnyUrl
  address: Stream(''),
  phone: Stream(''),
  hours: Stream(''),
  website: Stream(''), //AnyUrl = 'talahairstudio.com'
  initial: Stream(''),
  bullets: Stream(''),
  optional: Stream(''),
  media: Stream(['']),
  audio: Stream(['']),
  call: Stream(''),
  closing: Stream(''),
  fontcolor: Stream('#FFFFFF'),
  themecolor: Stream('#CC5500'),
  font: Stream('Segoe_UI_Bold'),
  duration: Stream(5),
}

