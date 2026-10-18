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
  // Any other refusal the server words for people -- the development login's
  // address, which nobody may register -- is shown as it stands.
  if (isSentence(detail)) return detail
  if (err && err.code == 422) {
    return 'That does not look like an email address.'
  }
  return 'Registration failed. Try again, or ask an administrator.'
}

/** A `detail` written for a person, rather than one of fastapi-users' codes.
 *
 * The codes are single upper-case words (`REGISTER_USER_ALREADY_EXISTS`); the
 * server's own refusals are sentences, and are meant to be read as they are.
 */
export function isSentence(detail) {
  return typeof detail == 'string' && /\s/.test(detail.trim())
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
          }, 'register'),
          m('button#forgot', {
            style: {
              display: User.username ? 'none' : ''
            },
            onclick: e => {
              e.preventDefault()
              askForReset(document.getElementById('username').value.trim())
            },
          }, 'forgot password')
        ]
      )
    ]
  }
}
}

/** Ask for a password-reset link to be mailed to `email`.
 *
 * The server answers the same whether or not the address has an account, so
 * that asking is no way to find out who has one; the message says so rather
 * than promising a mail. A server without mail sends nothing at all, which
 * only an administrator can change.
 */
export function askForReset(email) {
  if (!email) {
    error('Enter your email address, then ask again.', 5)
    return Promise.resolve(false)
  }
  return m
    .request('/auth/forgot-password', { method: 'POST', body: { email } })
    .then(
      () => {
        message(
          `If ${email} has an account, a link to choose a new password is on ` +
            'its way to it. If nothing arrives, ask an administrator.',
          12
        )
        return true
      },
      err => {
        error(
          err && err.code == 422
            ? 'That does not look like an email address.'
            : 'The reset could not be asked for. Try again.',
          6
        )
        return false
      }
    )
}

/** What to tell someone whose reset or confirmation link was refused. */
export function linkFailure(err) {
  const detail = err && err.response && err.response.detail
  if (detail == 'RESET_PASSWORD_BAD_TOKEN' || detail == 'VERIFY_USER_BAD_TOKEN') {
    return 'This link has expired or has been used already. Ask for a new one from the login screen.'
  }
  if (detail == 'VERIFY_USER_ALREADY_VERIFIED') {
    return 'This address is confirmed already.'
  }
  if (detail && detail.code == 'RESET_PASSWORD_INVALID_PASSWORD') {
    return `That password was refused: ${detail.reason}`
  }
  if (isSentence(detail)) return detail
  return 'That did not work. Open the link again, or ask for a new one.'
}

/** The page a mailed link opens: `#!/account/reset` or `#!/account/verify`.
 *
 * A password-reset or confirmation token used to be printed to the server's
 * log and go nowhere else, so outside development nobody could finish either.
 * The server mails them now, as a link here carrying the token, and this page
 * finishes the job: a new password for a reset, which then goes to the login
 * screen; the confirmation itself for a verify, as soon as the page opens.
 *
 * Open to anybody -- the person following the link is not logged in, which is
 * the point -- so the session guard leaves `/account/` alone (`User.js`).
 */
export const Account = () => {
  let sending = false
  let confirmed = null
  const token = () => m.route.param('token')
  const action = () => m.route.param('action')

  const confirm = () => {
    sending = true
    m.request('/auth/verify', { method: 'POST', body: { token: token() } })
      .then(
        () => {
          confirmed = 'Your address is confirmed.'
        },
        err => {
          confirmed = linkFailure(err)
        }
      )
      .finally(() => {
        sending = false
        m.redraw()
      })
  }

  const reset = e => {
    e.preventDefault()
    const password = document.getElementById('new-password').value
    const again = document.getElementById('confirm-password').value
    if (password.length < 8) {
      error('A password must be at least 8 characters.', 5)
      return
    }
    if (password != again) {
      error('The two passwords are not the same.', 5)
      return
    }
    sending = true
    m.request('/auth/reset-password', {
      method: 'POST',
      body: { token: token(), password },
    })
      .then(
        () => {
          success('Your password is set. Log in with it.', 8)
          m.route.set('/login')
        },
        err => error(linkFailure(err), 10)
      )
      .finally(() => {
        sending = false
        m.redraw()
      })
  }

  return {
    oninit: () => {
      if (action() == 'verify' && token()) confirm()
    },
    view: () => {
      if (!token() || !['reset', 'verify'].includes(action())) {
        return [
          m('h2', 'account'),
          m(
            'p#account-missing',
            'This page opens from the link in an email from this server, and ' +
              'that link is not here. Ask for a new one from the login screen.'
          ),
          m('a', { href: '#!/login' }, 'to the login screen'),
        ]
      }
      if (action() == 'verify') {
        return [
          m('h2', 'confirm your address'),
          m('p#account-outcome', confirmed || 'Confirming your address...'),
        ]
      }
      return [
        m('h2', 'choose a new password'),
        m('form#reset', { onsubmit: reset }, [
          m('label[for=new-password]', 'new password:'),
          m('input#new-password', { type: 'password', autocomplete: 'new-password' }),
          m('br'),
          m('label[for=confirm-password]', 'again:'),
          m('input#confirm-password', {
            type: 'password',
            autocomplete: 'new-password',
          }),
          m('br'),
          m('input#reset-submit', {
            type: 'submit',
            value: 'set password',
            disabled: sending,
          }),
        ]),
      ]
    },
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