import m from 'mithril'
import Project from './Project'
import { Home } from './Home'
import { Projects } from './Projects'
import { Documents } from './Documents'
import '../node_modules/alertifyjs/build/css/alertify.min.css'
import '../node_modules/alertifyjs/build/css/themes/semantic.css'
import { defaults } from 'alertifyjs'
import { Login, Logout } from './Login'
import { User } from './User'
import { Renders } from './Renders'
import { Magnussens } from './Magnussens'
import { Layout } from './Components'
import { TemplateEditor } from './TemplateEditor'
import { Otto } from './Otto'
import ICON from './assets/al-white.svg'

var state = require('./Globals').state

defaults.transition = 'zoom'
defaults.theme.ok = 'ui positive button'
defaults.theme.cancel = 'ui black button'
defaults.notifier.delay = 10

if (
  window.matchMedia &&
  window.matchMedia('(prefers-color-scheme: dark)').matches
) {
  // swap favicon if in dark mode
  let favicon = (document.getElementById('favicon').href = ICON)
}

window.addEventListener('storage', event => {
  let credentials = User.jwt
  // console.log('storage event', event, credentials)
  if (event.key === 'REQUESTING_SHARED_CREDENTIALS' && credentials) {
    window.localStorage.setItem(
      'CREDENTIALS_SHARING',
      JSON.stringify(credentials)
    )
    window.localStorage.removeItem('CREDENTIALS_SHARING')
  }
  if (event.key === 'CREDENTIALS_SHARING' && !credentials) {
    User.login(JSON.parse(event.newValue))
  }
  if (event.key === 'CREDENTIALS_FLUSH' && credentials) {
    User.logout()
  }
})

window.localStorage.setItem(
  'REQUESTING_SHARED_CREDENTIALS',
  Date.now().toString()
)
window.localStorage.removeItem('REQUESTING_SHARED_CREDENTIALS')

console.log('sup!')

m.route(document.body, '/', {
  '/': { render: () => m(Layout, m(Home)) },
  '/projects': { render: () => m(Layout, m(Projects)) },
  '/renders': { render: () => m(Layout, m(Renders)) },
  '/documents': { render: () => m(Layout, m(Documents)) },
  '/otto': Otto,
  '/form': { render: () => m(Layout, m(Magnussens)) },
  '/editor': { render: () => m(Layout, m(TemplateEditor)) },
  '/login': { render: () => m(Layout, m(Login)) },
  '/logout': { render: () => m(Layout, m(Logout)) },
})
