import m from 'mithril'
import { Menu } from './Menu'
import { User } from './User'
import jwt_decode from 'jwt-decode'
import { success, error, message, prompt } from 'alertifyjs'

const Login = () => {
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
                let decoded = jwt_decode(token['access_token'])
                User.username = decoded['sub']
                console.log('authenticated!', decoded)
                User.token = token['token_type'] + ' ' + token['access_token']
                User.loggedIn = true
                success(`${User.username} logged in!`, 4)
                console.log('User: ', User)
                if (m.route.param('redirect')) {
                  m.route.set(m.route.param('redirect'))
                } else {
                  m.route.set('/')
                }
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
                console.log('logged out')
                message(`${User.username} logged out`)
                User.username = null
                User.token = null
                User.loggedIn = false
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

export default Login
