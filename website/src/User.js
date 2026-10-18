import m from 'mithril'
import jwt_decode from 'jwt-decode'
import { message } from 'alertifyjs'
import { auth } from './Login'

const STORAGE_KEY = 'alfred.jwt'

/** Renew a token this long before it expires.
 *
 * Tokens live an hour (TOKEN_LIFETIME_SECONDS in alfred/core/routes/users.py),
 * and `/auth/jwt/refresh` only accepts one that still works -- so renewal has
 * to happen before expiry or not at all. Five minutes leaves room for a slow
 * request, or a timer a background tab has throttled, and still renews well
 * inside the lifetime.
 */
export const RENEW_BEFORE_MS = 5 * 60 * 1000

/** How long to wait after a renewal that failed without being refused.
 *
 * A server restarting or a dropped connection says nothing about the session,
 * and the token may well still be good. Try again on this cadence until it
 * actually runs out -- and no faster, however much the pointer moves.
 */
const RETRY_MS = 30 * 1000

/** Input that counts as somebody using the app. */
const ACTIVITY = ['pointerdown', 'keydown', 'wheel', 'touchstart', 'mousemove']

/** When `token` stops working, measured on this browser's clock (ms).
 *
 * Not simply `exp`. That is a moment on the server's clock, and a browser
 * running a few minutes slow would schedule its renewal after the token had
 * already died. The server now stamps `iat` as well, so the lifetime is
 * `exp - iat` in server time -- skew cancels -- counted down from the moment
 * this tab received the token.
 *
 * `expires_at` is this module's own note on a token it has already placed in
 * time, kept so a reload or another tab (see the credential sharing in
 * index.js) does not restart the countdown from zero. A token from a server
 * that does not send `iat` falls back to trusting the two clocks agree.
 */
/** Routes anybody may open: logging in and out, and the account pages.
 *
 * `/account/` is where a mailed reset or confirmation link lands, opened by
 * somebody who is by definition not logged in. The session guard used to
 * send every route but these two to the login screen, the reset page with
 * them -- and its token with it, out of the address bar.
 */
const PUBLIC_ROUTES = ['/login', '/logout', '/account/']

export function isPublicRoute(route) {
  return PUBLIC_ROUTES.some(prefix => (route || '').startsWith(prefix))
}

export function expiryOf(token, receivedAt = Date.now()) {
  if (typeof token.expires_at == 'number') return token.expires_at
  const { exp, iat } = jwt_decode(token.access_token)
  if (!exp) return null
  return iat ? receivedAt + (exp - iat) * 1000 : exp * 1000
}

export var User = {
  // The token as the server sent it, plus `expires_at`. Shared with other
  // tabs by index.js, which is why the expiry travels inside it.
  jwt: null,
  username: null,
  // The Authorization header value.
  token: null,
  loggedIn: false,
  devMode: false,
  // Set once restore and the dev-mode probe have both had their say.
  booted: false,
  // When the token stops working, and when this tab took it, both on this
  // browser's clock (ms).
  expiresAt: null,
  adoptedAt: null,
  // The last time anybody used this tab (ms).
  lastActivity: 0,
  renewal: null,
  renewing: null,
  backoffUntil: 0,
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

  /** Take a token: hold it, store it, and schedule its renewal.
   *
   * The one way a token enters this module, whether from a login, a renewal,
   * a reload or another tab.
   */
  adopt: token => {
    const expiresAt = expiryOf(token)
    User.jwt = { ...token, expires_at: expiresAt }
    User.token = token['token_type'] + ' ' + token['access_token']
    User.expiresAt = expiresAt
    User.adoptedAt = Date.now()
    // sessionStorage, not localStorage. The token is already put through
    // localStorage momentarily by the cross-tab credential sharing in
    // index.js, so this is not a new class of exposure -- but sessionStorage
    // is scoped to one tab and cleared when it closes, which is the weaker of
    // the two claims a stored token can make.
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(User.jwt))
    } catch (e) {
      // Private browsing can refuse storage. Staying logged in for this page
      // view is still better than failing.
    }
    User.schedule()
  },

  /** Forget the token everywhere this tab keeps it. */
  discard: () => {
    clearTimeout(User.renewal)
    User.renewal = null
    User.jwt = null
    User.token = null
    User.expiresAt = null
    User.adoptedAt = null
    try {
      window.sessionStorage.removeItem(STORAGE_KEY)
    } catch (e) {
      // nothing stored to clear
    }
  },

  expired: () => !!User.expiresAt && Date.now() >= User.expiresAt,

  /** Wake up shortly before the token expires. */
  schedule: (delay = null) => {
    clearTimeout(User.renewal)
    if (!User.expiresAt) return
    const wait =
      delay == null
        ? Math.max(0, User.expiresAt - RENEW_BEFORE_MS - Date.now())
        : delay
    User.renewal = setTimeout(User.due, wait)
  },

  /** The token is about to expire: renew it if this tab is in use.
   *
   * "In use" is any input since this tab took the current token. A tab left
   * alone for a whole token lifetime is not renewed: it lapses at expiry, so
   * an unattended session ends within two lifetimes of the last time anybody
   * touched it, rather than lasting for as long as the tab stays open.
   */
  due: () => {
    if (!User.token) return
    if (User.expired()) return User.lapse()
    if (User.lastActivity >= User.adoptedAt) return User.renew()
    User.schedule(Math.max(0, User.expiresAt - Date.now()))
  },

  /** The token ran out. Say so where somebody can see it.
   *
   * A hidden tab is left alone: it is sent to log in when it is next looked
   * at (see `returned`), not while nobody is watching -- and a session that
   * ended in a background tab overnight is not news until then.
   */
  lapse: () => {
    if (!User.token || !User.expired()) return
    if (document.visibilityState == 'hidden') return
    User.expire()
  },

  /** Exchange the current token for a fresh one. One request at a time.
   *
   * Resolves true when a new token was adopted. A refusal (401) means the
   * session is over and sends the person to log in; any other failure keeps
   * the token, which may well still work, and tries again later.
   */
  renew: () => {
    if (User.renewing) return User.renewing
    const token = User.token
    if (!token || Date.now() < User.backoffUntil) return Promise.resolve(false)
    User.renewing = m
      .request('/auth/jwt/refresh', {
        method: 'POST',
        headers: { Authorization: token },
        // Nothing on screen depends on the token itself.
        background: true,
      })
      .then(
        fresh => {
          // A logout, or another login, while this was in flight wins.
          if (User.token != token) return false
          User.backoffUntil = 0
          User.adopt(fresh)
          return true
        },
        err => {
          if (User.token != token) return false
          if (err.code == 401) {
            User.expire()
            return false
          }
          User.backoffUntil = Date.now() + RETRY_MS
          User.schedule(RETRY_MS)
          return false
        }
      )
      .finally(() => {
        User.renewing = null
      })
    return User.renewing
  },

  /** Somebody touched the app. Cheap: usually only records the time.
   *
   * Inside the renewal window this renews straight away, so a person who
   * comes back with minutes to spare is not logged out by a timer that had
   * already decided they were gone.
   */
  used: () => {
    User.lastActivity = Date.now()
    if (!User.token || !User.expiresAt) return
    if (User.expired()) return User.expire()
    if (User.expiresAt - Date.now() <= RENEW_BEFORE_MS) User.renew()
  },

  /** The window regained focus, or the tab became visible.
   *
   * The moment most likely to find a stale session: background tabs have
   * their timers throttled, and a laptop lid stops them altogether. A token
   * that ran out meanwhile goes to the login screen now, before the person
   * starts work that would fail; one more than half spent is renewed, so a
   * timer that fired late cannot strand it.
   */
  returned: () => {
    User.lastActivity = Date.now()
    if (!User.token || !User.expiresAt) return
    if (User.expired()) return User.expire()
    const span = User.expiresAt - User.adoptedAt
    if (User.expiresAt - Date.now() < span / 2) User.renew()
  },

  /** The session is over: the token expired, or the server refused it.
   *
   * Sends the person to log in with a way back to where they were. Renewal
   * cannot rescue this -- `/auth/jwt/refresh` takes a token that still works,
   * which is why the old retry-on-401 never once renewed anything and every
   * session simply ended after an hour.
   */
  expire: () => {
    const hadSession = !!User.token || User.loggedIn
    User.discard()
    User.username = null
    User.loggedIn = false
    if (!hadSession) return
    const route = m.route.get() || ''
    if (isPublicRoute(route)) {
      m.redraw()
      return
    }
    message('Your session ended. Log in to carry on where you were.', 8)
    User.toLogin(route)
  },

  /** Go to the login screen, carrying `route` to come back to afterwards.
   *
   * Encoded once more than `m.route.set` encodes it. mithril's router
   * URI-decodes the whole hash before it splits off the query, then decodes
   * each value again -- so a route carrying its own query, `/?stage=render`,
   * arrived as `redirect=/?stage=render`, split on its second `=`, and came
   * back as an empty string. Every return to where you were with a stage or
   * a project in it landed on `/`: the session guard's and the expiry's alike.
   */
  toLogin: route => {
    m.route.set('/login', { redirect: encodeURIComponent(route) })
  },

  /** The route `toLogin` carried, or null. */
  returnRoute: () => {
    const target = m.route.param('redirect')
    if (!target || typeof target != 'string') return null
    // A route starts with `/`. Anything else is still encoded: a router that
    // decoded it once rather than twice.
    try {
      return target.startsWith('/') ? target : decodeURIComponent(target)
    } catch (e) {
      return null
    }
  },

  // Restored before routing, so a guarded view does not redirect to /login in
  // the moment before the session comes back.
  restore: () => {
    try {
      const stored = window.sessionStorage.getItem(STORAGE_KEY)
      if (!stored) return false
      const token = JSON.parse(stored)
      // Expired tokens are worse than none: they let the UI render as logged
      // in and then fail every request with a 401.
      const expiresAt = expiryOf(token)
      if (expiresAt && expiresAt <= Date.now()) {
        window.sessionStorage.removeItem(STORAGE_KEY)
        return false
      }
      User.adopt(token)
      // A reload is use.
      User.lastActivity = Date.now()
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
          User.discard()
          return false
        }
      )
    } catch (e) {
      User.discard()
      return false
    }
  },
  login: token => {
    User.adopt(token)
    // Logging in is use.
    User.lastActivity = Date.now()
    auth('/users/me').then(
      me => {
        User.username = me.first_name
        User.loggedIn = true
        // Go somewhere that is not the login screen.
        //
        // This checked `m.route.get() == '/login'`, which is false the moment
        // the route carries a query string -- and the session guard sends
        // people here as `/login?redirect=...`. So an empty or absent redirect
        // fell through to `m.route.set(m.route.get())`, which re-set the login
        // route and left the person looking at the form they had just
        // submitted.
        const target = User.returnRoute()
        const onLogin = (m.route.get() || '').split('?')[0].startsWith('/login')
        if (target && !target.split('?')[0].startsWith('/login')) {
          m.route.set(target)
        } else if (onLogin) {
          m.route.set('/')
        } else {
          m.route.set(m.route.get())
        }
      },
      err => {
        console.log('error getting username', err)
      }
    )
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
    if (isPublicRoute(route)) return
    User.toLogin(route)
  },

  /** End the session: here, in every other tab, and at the server.
   *
   * This posted to `/logout`, which is not a route on this server; the
   * request fell through to the static mount and answered 405, unread. It
   * calls fastapi-users' own `/auth/jwt/logout` now, with the token it is
   * ending. These are stateless JWTs, so the server cannot revoke one -- what
   * actually ends the session is this tab forgetting the token, which happens
   * first and does not wait on the answer.
   */
  logout: () => {
    console.log('logging out', User.username)
    const token = User.token
    User.discard()
    User.username = null
    User.loggedIn = false
    if (token) {
      m.request('/auth/jwt/logout', {
        method: 'POST',
        headers: { Authorization: token },
        background: true,
      }).catch(() => {
        // Already logged out here; an expired token is refused, and that is fine.
      })
    }
    try {
      window.localStorage.setItem('CREDENTIALS_FLUSH', Date.now().toString())
      window.localStorage.removeItem('CREDENTIALS_FLUSH')
    } catch (e) {
      // No other tabs to tell.
    }
    m.route.set('/login')
  },
}

// Watching for use. Passive listeners on window, and each only records a time
// unless the token is close to running out, so following the pointer costs
// next to nothing.
if (typeof window != 'undefined') {
  const used = () => User.used()
  for (const type of ACTIVITY) {
    window.addEventListener(type, used, { capture: true, passive: true })
  }
  window.addEventListener('focus', () => User.returned())
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState == 'visible') User.returned()
  })
}
