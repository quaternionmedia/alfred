import m from "mithril";
import Slider from './Slider'
import { Timeline } from './Timeline'
import Monitor from './Monitor'
import Project from './Project'
import Tools from './Tools'
import TimelineTools from './TimelineTools'
import Scale from './Scale'
import { Menu } from './Menu'
import Home from './Home'
import Projects from './Projects'
import '../node_modules/alertifyjs/build/css/alertify.min.css'
import '../node_modules/alertifyjs/build/css/themes/semantic.css'
import { defaults } from 'alertifyjs'
import Login from './Login'
import Bin from './Bin'
import { Import } from './Import'
import { Renders } from './Renders'
import { OttoTimeline } from './OttoTimeline'
import { Preview } from './Preview'
import { FormPage } from './Form'
import { Resolution } from './Resolution'

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
      m(TimelineTools),
      m(Timeline),
      m('#scalecontainer', {style:
        {display: 'inline-flex', width:'95vw'}}, [
        m('i.material-icons', {style: {position: 'absolute',}}, 'zoom_out'),
        m('i.material-icons', {style: {position: 'absolute', right:0}}, 'zoom_in'),
        m(Scale),
      ]),
      m(Project),
      m(Import),
      m(Bin),
    ]
  }
}

var Otto = {
  view: (vnode) => {
    return [
      m(Menu),
      m('#head.head', [
        m(Preview)
      ]),
      m(Resolution, [
        '1920x1080',
        '1280x720',
        '1024x768',
        '800x600',
        '640x480',
        '480x320',
        '200x200',
      ]),
      m(Tools),
      m(Slider),
      m(TimelineTools),
      m(OttoTimeline),
      m('#scalecontainer', {style:
        {display: 'inline-flex', width:'95vw'}}, [
        m('i.material-icons', {style: {position: 'absolute',}}, 'zoom_out'),
        m('i.material-icons', {style: {position: 'absolute', right:0}}, 'zoom_in'),
        m(Scale),
      ]),
      m(Import),
      m(Bin),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", {
  "/": Home,
  '/projects': Projects,
  '/editor': Editor,
  '/otto': Otto,
  '/renders': Renders,
  '/login': Login,
  '/form': FormPage,
} );
