import m from "mithril";
import Slider from './Slider'
// import { Timeline } from './Timeline'
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
import { Login } from './Login'
import { User } from './User'
import Bin from './Bin'
import { Import } from './Import'
import { Renders } from './Renders'
import { OttoTimeline } from './OttoTimeline'
import { Preview } from './Preview'
import { FormPage } from './Form'
var state = require("./Globals").state

defaults.transition = "zoom"
defaults.theme.ok = "ui positive button"
defaults.theme.cancel = "ui black button"
defaults.notifier.delay = 10

window.addEventListener('storage', (event) => {
  let credentials = User.jwt
  // console.log('storage event', event, credentials)
  if (event.key === 'REQUESTING_SHARED_CREDENTIALS' && credentials) {
    window.localStorage.setItem('CREDENTIALS_SHARING', JSON.stringify(credentials))
    window.localStorage.removeItem('CREDENTIALS_SHARING')
  }
  if (event.key === 'CREDENTIALS_SHARING' && !credentials) {
    User.login(JSON.parse(event.newValue))
  }
  if (event.key === 'CREDENTIALS_FLUSH' && credentials) {
    User.logout()
  }
})

window.localStorage.setItem('REQUESTING_SHARED_CREDENTIALS', Date.now().toString())
window.localStorage.removeItem('REQUESTING_SHARED_CREDENTIALS')

var Otto = {
  view: (vnode) => {
    return [
      m(Menu),
      m('#head.head', {style: {
        width: `${state.width()/state.height()*40}vh`,
        height: '40vh'
      }}, [
        m(Preview)
      ]),
      m(Tools),
      m(Slider),
      m('.bar', {}, [
        m(TimelineTools),
        m(OttoTimeline),
      ]),
      m('#scalecontainer', {style:
        {display: 'inline-flex', width:'95vw'}}, [
        m('i.material-icons', 'zoom_out'),
        m(Scale),
        m('i.material-icons', {style: {position: 'absolute', right:0}}, 'zoom_in'),
      ]),
      m(Bin),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", {
  "/": Home,
  '/projects': Projects,
  '/otto': Otto,
  '/renders': Renders,
  '/login': Login,
  '/form': FormPage,
} );
