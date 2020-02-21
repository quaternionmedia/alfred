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
import '../node_modules/alertifyjs/build/css/alertify.min.css'
import '../node_modules/alertifyjs/build/css/themes/semantic.css'
import { defaults } from 'alertifyjs'

defaults.transition = "zoom"
defaults.theme.ok = "ui positive button"
defaults.theme.cancel = "ui black button"
defaults.notifier.delay = 10

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
      m('#spacer'),
      m(Timeline),
      m('#scalecontainer', {style:
        {display: 'inline-flex', width:'95vw'}}, [
        m('i.material-icons', {style: {position: 'absolute',}}, 'zoom_out'),
        m('i.material-icons', {style: {position: 'absolute', right:0}}, 'zoom_in'),
        m(Scale),
      ]),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", {
  "/": Home,
  '/projects': Projects,
  '/editor': Editor,
} );
