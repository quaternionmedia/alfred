import m from 'mithril'
import Project from './Project'
import { Documents } from './Documents'
import '../node_modules/alertifyjs/build/css/alertify.min.css'
import '../node_modules/alertifyjs/build/css/themes/semantic.css'
import { defaults } from 'alertifyjs'
import { Login, Logout } from './Login'
import { User } from './User'
import { Magnussens } from './Magnussens'
import { Layout } from './Components'
import { TemplateEditor } from './TemplateEditor'
import { Otto } from './Otto'
// Same as the logo in Menu.js: the default import is not a URL string.
const ICON = new URL('./assets/al-white.svg', import.meta.url).href

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
  document.getElementById('favicon').href = ICON
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

// Restore a stored session, then ask the server whether auth is disabled --
// both before routing. Routing first would let a guarded view redirect to
// /login in the moment before either answer arrives, which is the flicker this
// is meant to remove.
//
// Only probe for the bypass if there is no session to restore; with one, the
// probe is a wasted request that would report devMode for an ordinary login.
// Restore a session, or find out the server has auth disabled, and only then
// decide whether this visitor has to log in. Both resolve asynchronously, so
// the guard waits for whichever ran -- redirecting before they answer would
// bounce somebody who is in fact logged in.


m.route(document.body, '/', {
  // The timeline is the entry point.
  //
  // `/` used to render a marketing homepage: four screenshots and a Hitchcock
  // quote, so the first thing the app showed was a description of itself
  // rather than the thing it does. It is gone, and with it four images loaded
  // from images.squarespace-cdn.com -- which AGENTS.md forbids and the
  // adoption record lists as an open governance gap.
  '/': Otto,
  // Migrated into the stage flow.
  //
  // Both of these listed data the flow also lists, fetched separately and
  // rendered differently -- two project lists and two render lists, each with
  // its own state, neither telling the other when anything changed. The flow's
  // versions carry what these did and more, so these redirect rather than
  // linger as a second way to see the same thing.
  //
  // Kept as redirects rather than deleted: they are the URLs the menu used,
  // that anyone has bookmarked, and that older docs name.
  '/projects': {
    onmatch: () => {
      m.route.set('/', { stage: 'source' })
    },
  },
  '/renders': {
    onmatch: () => {
      m.route.set('/', { stage: 'deliver' })
    },
  },
  '/documents': { render: () => m(Layout, m(Documents)) },
  '/otto': Otto,
  '/form': { render: () => m(Layout, m(Magnussens)) },
  '/editor': { render: () => m(Layout, m(TemplateEditor)) },
  '/login': { render: () => m(Layout, m(Login)) },
  '/logout': { render: () => m(Layout, m(Logout)) },
})

// Session restore and the guard run *after* the router is mounted.
//
// Placed above `m.route(...)` these raced it: for a deep link the redirect
// fired during routing and worked, and for `/` the promise resolved before the
// router existed, so `m.route.set` had nothing to set and an anonymous visitor
// sat on the editor shell. Routing first, then decide.
// `restore` resolves false when there is nothing stored, or when what was
// stored no longer works; only then is the dev-mode probe worth making.
Promise.resolve(User.restore())
  .then(restored => (restored ? true : User.detectDevMode()))
  .catch(() => false)
  .then(() => {
    User.booted = true
    User.requireSession()
  })
