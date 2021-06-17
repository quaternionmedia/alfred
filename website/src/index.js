import m from "mithril"
import Project from './Project'
import { Menu } from './Menu'
import Home from './Home'
import Projects from './Projects'
import '../node_modules/alertifyjs/build/css/alertify.min.css'
import '../node_modules/alertifyjs/build/css/themes/semantic.css'
import { defaults } from 'alertifyjs'
import { Login } from './Login'
import { User } from './User'
import { Renders } from './Renders'
import { Magnussens } from './Magnussens'
import { Layout } from './Components'

import { Otto } from './Otto'


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

console.log('sup!')

m.route(document.body, "/", {
  "/": Home,
  '/projects': Projects,
  '/otto': Otto,
  '/form': { render: () => m(Layout, m(Magnussens))},
  '/renders': { render: () => m(Layout, m(Renders))},
  '/login': { render: () => m(Layout, m(Login))},
} );
