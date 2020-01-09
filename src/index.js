import m from "mithril";
// var Slider = require("./Slider")
import Slider from './Slider'
var Timeline = require("./Timeline").Timeline
// import Timeline from './Timeline'
import Monitor from './Monitor'
import Project from './Project'
import Tools from './Tools'
import Scale from './Scale'

var Al = {
  view: (vnode) => {
    return [
      m('span#main', {}, [
        m('h3.title', {align: 'center'}, 'Alfred. The serverless video editor'),
      ]),
      m('#head.head', [
        m(Project),
        m(Tools),
        m(Monitor, {}),
      ]),
      m(Slider),
      m(Timeline),
      m(Scale),
      // m(resizable),
      // m(sortable),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
