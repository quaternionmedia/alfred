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
  // sessionStorage, not localStorage. The token is already put through
  // localStorage momentarily by the cross-tab credential sharing below, so
  // this is not a new class of exposure -- but sessionStorage is scoped to one
  // tab and cleared when it closes, which is the weaker of the two claims a
  // stored token can make.
  //
  // Restored before routing, so a guarded view does not redirect to /login in
  // the moment before the session comes back.
  restore: () => {
    try {
      const stored = window.sessionStorage.getItem('alfred.jwt')
      if (!stored) return false
      const token = JSON.parse(stored)
      const decoded = jwt_decode(token['access_token'])
      // Expired tokens are worse than none: they let the UI render as logged
      // in and then fail every request with a 401.
      if (decoded.exp && decoded.exp * 1000 <= Date.now()) {
        window.sessionStorage.removeItem('alfred.jwt')
        return false
      }
      User.jwt = token
      User.token = token['token_type'] + ' ' + token['access_token']
      auth('/users/me').then(
        me => {
          User.username = me.first_name
          User.loggedIn = true
          m.redraw()
        },
        () => {
          User.logout()
        }
      )
      return true
    } catch (e) {
      window.sessionStorage.removeItem('alfred.jwt')
      return false
    }
  },
  login: (token) => {
    User.jwt = token
    let decoded = jwt_decode(token['access_token'])

    try {
      window.sessionStorage.setItem('alfred.jwt', JSON.stringify(token))
    } catch (e) {
      // Private browsing modes can refuse storage. Staying logged in for this
      // page view is still better than failing the login.
    }

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
    try {
      window.sessionStorage.removeItem('alfred.jwt')
    } catch (e) {
      // nothing stored to clear
    }
    window.localStorage.setItem('CREDENTIALS_FLUSH', Date.now().toString())
    window.localStorage.removeItem('CREDENTIALS_FLUSH')
    m.route.set('/')
  }
}
