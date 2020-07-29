import m from 'mithril'
import { Menu } from './Menu'
import { User } from './User'
import { success, error, message, prompt } from 'alertifyjs'

export function auth(url, opts) {
  const req = new Promise((resolve, reject) => {
      m.request(url, {
        headers: {
          Authorization: User.token,
        },
        ...opts
      }).then(res => {
        console.log('auth success')
        resolve(res)
        // return res
      }).catch( e => {
        if (e.code == 401) {
          m.request('/refresh', {
            method: 'post'
        }).then(token => {
            User.login(token)
            auth(url, opts).then(res => {
              console.log('resolved refresh')
              resolve(res)
            })
          }).catch(err => {
            console.log('error making auth request', url, opts, err)
            error('Not authorized')
            m.route.set('/login', {
                redirect: m.route.get()
              })
            reject(err)
          })
        }
      })
    })
    return req
}

export const Login = () => {
  return {
    view: (vnode) => {
      return [
        m(Menu),
        m('h2', 'login'),
        m('form#login', {
          action: '/token',
          method: 'post',
        }, [
          m('label[for=username]', 'username:'),
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
              m.request('/token', {
                method: 'post',
                body: form,
              }).then( (token) => {
                User.login(token)
                success(`${User.username} logged in!`, 4)
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
                logout()
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
              prompt('register', 'what is your email address?', 'e@mail.com', (e, v) => {
                let form = new FormData(document.getElementById('login'))
                form.append('email', v)
                console.log('registering user', e, v, form)
                m.request({
                  url: '/register',
                  method: 'post',
                  body: form
                }).then( res => {
                  console.log('successfully registered', res)
                  success(`${v} is now registered!`)
                }).catch( err => {
                  error('error regestering')
                })
              }, () => {
              })
            },
          }, 'register')
        ]
      )
    ]
  }
}
}
