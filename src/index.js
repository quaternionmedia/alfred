import m from "mithril";
var Slider = require("./Slider")
var Timeline = require("./Timeline")
import Monitor from './Monitor'

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'Alfred. The serverless video editor'),
      m(Monitor, {src: 'videos/19-100k.mp4'}),
      m(Slider),
      m(Timeline),
      // m(resizable),
      // m(sortable),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
