import m from 'mithril'
import jwt_decode from 'jwt-decode'
import { auth } from './Login'

export var User = {
  jwt: null,
  username: null,
  token: null,
  loggedIn: false,
  devMode: false,
  // Set once restore and the dev-mode probe have both had their say.
  booted: false,
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
      // Resolves when the session is *confirmed*, not when it is attempted.
      //
      // This returned true synchronously while `loggedIn` was still false
      // until /users/me answered. The boot guard read that as "restored", ran
      // immediately, saw `loggedIn` false and sent a perfectly good session to
      // the login screen -- so a reload logged you out, which is the exact
      // behaviour the stored token exists to prevent.
      return auth('/users/me').then(
        me => {
          User.username = me.first_name
          User.loggedIn = true
          m.redraw()
          return true
        },
        () => {
          window.sessionStorage.removeItem('alfred.jwt')
          return false
        }
      )
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
      // Go somewhere that is not the login screen.
      //
      // This checked `m.route.get() == '/login'`, which is false the moment
      // the route carries a query string -- and the session guard sends people
      // here as `/login?redirect=...`. So an empty or absent redirect fell
      // through to `m.route.set(m.route.get())`, which re-set the login route
      // and left the person looking at the form they had just submitted.
      const target = m.route.param('redirect')
      const onLogin = (m.route.get() || '').split('?')[0].startsWith('/login')
      if (target && !target.split('?')[0].startsWith('/login')) {
        m.route.set(target)
      } else if (onLogin) {
        m.route.set('/')
      } else {
        m.route.set(m.route.get())
      }
    }, err => {
      console.log('error getting username', err)
    })
    
    // m.redraw()
  },
  /** Send an anonymous visitor to the login screen, once boot has settled.
   *
   * The app is entirely gated: every view needs a session. That used to be
   * enforced by accident -- each view fetched something, `auth` saw the 401 and
   * redirected. Migrating #!/projects and #!/renders into the stage flow
   * removed the accident: the flow's panels skip their fetches when there is no
   * session, so an anonymous visitor landed on the editor shell and sat there.
   *
   * Called after `restore` and `detectDevMode` have settled, because both
   * resolve asynchronously and redirecting before they answer would bounce
   * somebody who is in fact logged in.
   */
  requireSession: () => {
    // Nothing to decide until boot has answered. Called from a component's
    // oninit this fires on the first draw, long before /users/me returns, and
    // would bounce a session that is about to be confirmed.
    if (!User.booted) return
    if (User.loggedIn) return
    const route = m.route.get() || ''
    if (route.startsWith('/login') || route.startsWith('/logout')) return
    m.route.set('/login', { redirect: route })
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
