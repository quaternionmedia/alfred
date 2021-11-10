import m from 'mithril'
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
        // console.log('auth success')
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
            if (err.code == 401) {
              error('not authorized', 2)
              m.route.set('/login', {
                redirect: m.route.get()
              })
            }
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