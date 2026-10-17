import m from 'mithril'
import { User } from './User'
import { success, error, message, prompt } from 'alertifyjs'

/** `m.request` with the session token, a way back from a 401, and a redraw.
 *
 * A 401 means the session is over -- the token expired, or the server no
 * longer accepts it -- and the caller should not have to know what to do
 * about that. Three things here are load-bearing and were learned the hard
 * way.
 *
 * **A 401 goes to the login screen, carrying the route.** This used to try
 * `/auth/jwt/refresh` first. That route only accepts a token that still
 * works, so asking it *after* a 401 could never succeed: the retry renewed
 * nothing, ever, and every session simply ended an hour after login. Renewal
 * now happens before expiry, while the app is in use (`User.renew`), and a 401
 * means exactly what it says. The one retry left is for a request that raced
 * a renewal: refused with the old token while the new one was arriving.
 *
 * **It redraws after the caller has stored the result.** `m.request` redraws
 * by itself, but that happens when *mithril's* promise settles -- before the
 * `.then` on this wrapper's promise runs. So a caller doing
 * `auth('/project').then(p => { Flow.projects = p })` assigns one redraw too
 * late, and the new data sits in module state with nothing on screen showing
 * it. It looked intermittent rather than broken, because any other response
 * arriving afterwards redrew and swept the earlier one in: the project list
 * appeared only when `/destinations` happened to answer last. Deep links were
 * the reliable failure -- opening `?project=<id>` directly showed an empty
 * timeline, while clicking the same project worked, because a DOM event
 * handler redraws on its own.
 *
 * The redraw is queued as a task, not a microtask, so it lands after a caller
 * chain of any length. `m.redraw` coalesces on an animation frame, so calling
 * it once per request costs nothing when several are in flight.
 *
 * **Every path settles the promise.** The retry branch used to be the only
 * one: a response that was not a 401 -- a 500, a dropped connection, a CORS
 * refusal -- matched no branch and returned without resolving or rejecting,
 * so the caller waited forever. Nothing timed out and nothing was logged; the
 * button just stayed spinning.
 */
export function auth(url, opts = {}) {
  // Headers merge rather than replace: a caller adding one of its own used to
  // drop the token along with the defaults. No header at all without a
  // token, rather than the string "null".
  const request = token =>
    m.request(url, {
      ...opts,
      headers: {
        ...(token ? { Authorization: token } : {}),
        ...(opts.headers || {}),
      },
    })

  const ended = e => {
    if (e.code == 401) User.expire()
    throw e
  }

  const sent = User.token
  const req = request(sent).catch(e => {
    if (e.code != 401) throw e
    // Renewed while this was in flight: the refusal was for the old token.
    if (User.token && User.token != sent) return request(User.token).catch(ended)
    return ended(e)
  })

  // Registered on `req` before the caller chains onto it, so this handler runs
  // first -- and defers, so the redraw itself runs after the caller's.
  req.finally(() => setTimeout(m.redraw, 0)).catch(() => {})
  return req
}

/** What to tell someone whose registration was refused.
 *
 * Every failure used to read "error regestering". The one that most needs
 * saying plainly is a server that does not take registrations at all -- closed
 * by default in production -- because nothing the person can type will fix it,
 * and a generic error invites them to keep trying. The server's own wording is
 * shown when it gives one, so the message cannot drift from the policy.
 */
export function registrationFailure(err) {
  const detail = err && err.response && err.response.detail
  if (err && err.code == 403) {
    return typeof detail == 'string'
      ? detail
      : 'Registration is closed on this server. Ask an administrator for an account.'
  }
  if (detail == 'REGISTER_USER_ALREADY_EXISTS') {
    return 'That email address already has an account. Log in instead.'
  }
  if (detail && detail.code == 'REGISTER_INVALID_PASSWORD') {
    return `That password was refused: ${detail.reason}`
  }
  if (err && err.code == 422) {
    return 'That does not look like an email address.'
  }
  return 'Registration failed. Try again, or ask an administrator.'
}

export const Login = () => {
  return {
    view: (vnode) => {
      return [
        m('h2', 'login'),
        m('form#login', {
          action: '/auth/jwt/login',
          method: 'post',
        }, [
          m('label[for=username]', 'email:'),
          m('input#username', {
            name: 'username',
          }),
          m('br'),
          m('label[for=password]', 'password:'),
          m('input#password', {
            name: 'password',
            type: 'password',
          }),
          m('br'),
          m('input#submit', {
            type: 'submit',
            value: 'login',
            style: {
              display: User.username ? 'none' : ''
            },
            onclick: (e) => {
              e.preventDefault()
              let form = new FormData(document.getElementById('login'))
              console.log('sending form', e, form)
              m.request('/auth/jwt/login', {
                method: 'post',
                body: form,
              }).then( (token) => {
                User.login(token)
                success(`Logged in!`, 4)
              }, (res) => {
                console.log('error logging in!', res)
                error('error logging in', 3)
              })
            }},
          ),
          m('button#logout', {
            style: {
              display: User.username ? '' : 'none'
            },
            onclick: (e) => {
              e.preventDefault()
              if (User.username) {
                User.logout()
              } else {
                message("not logged in. Can't log out.", 3)
              }
            }
          }, 'logout'),
          m('button#register', {
            style: {
              display: User.username ? 'none' : ''
            },
            onclick: e => {
              e.preventDefault()
              if (document.getElementById('username').value == '') {
                error('please enter a username')
              } else if (document.getElementById('password').value.length < 8) {
                error('password must be at least 8 characters')
              } else {
                prompt('register', 'what is your first name?', 'user', (e, first_name) => {
                  let form = new FormData(document.getElementById('login'))
                  let register = {first_name: first_name, email: form.get('username'), password: form.get('password')}
                  console.log('registering user', register, e, form)
                  m.request({
                    url: '/auth/register',
                    method: 'post',
                    body: register
                  }).then( res => {
                    console.log('successfully registered', res)
                    success(`${res.first_name} is now registered!`)
                  }).catch( err => {
                    console.log('error registering', err)
                    error(registrationFailure(err), 8)
                  })
                }, () => {
                })
              }
            },
          }, 'register')
        ]
      )
    ]
  }
}
}

/** The /logout route: end the session once, on arrival.
 *
 * This logged out from `view`, which mithril calls on every redraw: a side
 * effect in the one function that should only draw, repeated by any redraw
 * that landed before the route changed. Arriving is the event; drawing is not.
 */
export const Logout = () => {
  return {
    oninit: () => {
      const hadSession = User.loggedIn || !!User.token
      User.logout()
      if (hadSession) message('logged out', 3)
    },
    view: () => null,
  }
}