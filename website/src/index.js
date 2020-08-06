import m from "mithril";
import Slider from './Slider'
// import { Timeline } from './Timeline'
import Monitor from './Monitor'
import Project from './Project'
import { PlaybackTools, SpeedTools, ProjectTools } from './Tools'
import TimelineTools from './TimelineTools'
import { Scale } from './Scale'
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
import { Timecode } from './Timecode'
import { Head } from './Head'
import { Resolution, Aspect } from './Resolution'

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
      m(Head, [
        m(Preview)
      ]),
      m('.bar.right', {}, [
        m(Aspect, [
          '16:9',
          '4:3',
          '4:5',
          '1:1',
          '5:4',
          '3:4',
          '9:16'
        ]),
        m(Resolution, [
          '1080p',
          '720p',
          '480p',
          '240p',
        ]),
      ]),
      m(PlaybackTools),
      m('.bar', {}, [
        m(Timecode),
        m(Slider),
      ]),
      m(SpeedTools),
      m('.bar', {}, [
        m(TimelineTools),
        m('.vcenter', {}, [
          m(OttoTimeline),
        ]),
      ]),
      m(Scale),
      m('.bar.right', {}, [
        m(ProjectTools),
      ]),
      m('.spacer', {style:{height:'3em'}}, []),
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
