import m from 'mithril'
import { User } from './User'
import { success, error, message, prompt } from 'alertifyjs'

/** `m.request` with the session token, a single retry on expiry, and a redraw.
 *
 * The wrapper exists for the retry: a 401 means the JWT expired, and the
 * caller should not have to know that. Two things about it are load-bearing
 * and were learned the hard way.
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
export function auth(url, opts) {
  const request = () =>
    m.request(url, {
      headers: { Authorization: User.token },
      ...opts,
    })

  const req = request().catch(e => {
    if (e.code != 401) throw e

    return m
      .request('/auth/jwt/refresh', {
        headers: { Authorization: User.token },
        method: 'post',
      })
      .then(token => {
        User.login(token)
        return request()
      })
      .catch(err => {
        // The refresh itself was rejected: the session is over, not stale.
        // Send them to login with a way back to where they were.
        if (err.code == 401) {
          error('not authorized', 2)
          m.route.set('/login', { redirect: m.route.get() })
        }
        throw err
      })
  })

  // Registered on `req` before the caller chains onto it, so this handler runs
  // first -- and defers, so the redraw itself runs after the caller's.
  req.finally(() => setTimeout(m.redraw, 0)).catch(() => {})
  return req
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
                    error('error regestering')
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

export const Logout = () => {
  return {
    view: vnode => {
      User.logout()
      message('logged out', 3)
    }
  }
}