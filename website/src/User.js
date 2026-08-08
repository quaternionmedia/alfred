import m from 'mithril'
import jwt_decode from 'jwt-decode'
import { auth } from './Login'

export var User = {
  jwt: null,
  username: null,
  token: null,
  loggedIn: false,
  devMode: false,
  // Detects the server-side auth bypass (ALFRED_DEV_SKIP_AUTH) by asking for
  // the current user with no credentials. With auth on that is a 401 and
  // nothing changes; with the bypass on it returns the dev user, so the SPA
  // can skip the login screen instead of merely tolerating an API that no
  // longer refuses it.
  //
  // Probing the server rather than reading a build-time flag keeps the two
  // from disagreeing: the frontend is a static bundle that outlives any
  // particular backend, so a baked-in constant would eventually be wrong.
  detectDevMode: () => {
    return m
      .request('/users/me')
      .then(me => {
        User.devMode = true
        User.loggedIn = true
        User.username = me.first_name || me.email
        console.warn('auth is disabled on the server; running as', User.username)
        m.redraw()
        return true
      })
      .catch(() => false)
  },
  login: (token) => {
    User.jwt = token
    let decoded = jwt_decode(token['access_token'])
    
    console.log('authenticated!', decoded)
    User.token = token['token_type'] + ' ' + token['access_token']
    auth('/users/me').then(me => {
      User.username = me.first_name
      User.loggedIn = true
      console.log('logged in as: ', User)
      if (m.route.param('redirect')) {
        m.route.set(m.route.param('redirect'))
      } else if (m.route.get() == '/login') {
        m.route.set('/')
      } else {
        m.route.set(m.route.get())
      }
    }, err => {
      console.log('error getting username', err)
    })
    
    // m.redraw()
  },
  logout: () => {
    console.log('logging out', User)
    m.request('/logout', {method: 'post'})
    User.jwt = null
    User.username = null
    User.token = null
    User.loggedIn = false
    window.localStorage.setItem('CREDENTIALS_FLUSH', Date.now().toString())
    window.localStorage.removeItem('CREDENTIALS_FLUSH')
    m.route.set('/')
  }
}
