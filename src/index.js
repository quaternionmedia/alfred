import m from "mithril";
import Slider from './Slider'
var Timeline = require("./Timeline").Timeline
import Monitor from './Monitor'
import Project from './Project'
import Tools from './Tools'
import Scale from './Scale'
import { Menu } from './Menu'
import Home from './Home'
import Projects from './Projects'

var Editor = {
  view: (vnode) => {
    return [
      m(Menu),
      m('#head.head', [
        m(Monitor, {}),
      ]),
      m(Tools),
      m(Slider),
      m(Project),
      m(Timeline),
      m(Scale),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", {
  "/": Home,
  '/projects': Projects,
  '/editor': Editor,
} );
