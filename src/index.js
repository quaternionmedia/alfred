import m from "mithril";
// var Slider = require("./Slider")
import Slider from './Slider'
var Timeline = require("./Timeline").Timeline
// import Timeline from './Timeline'
import Monitor from './Monitor'
import Project from './Project'
import Tools from './Tools'

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'Alfred. The serverless video editor'),
      m('#head.head', [
        m(Project),
        m(Tools),
        m(Monitor, {}),
      ]),
      m(Slider),
      m(Timeline),
      // m(resizable),
      // m(sortable),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
