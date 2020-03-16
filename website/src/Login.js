import m from 'mithril'
import { Menu } from './Menu'
import { User } from './User'
import jwt_decode from 'jwt-decode'
import { success, error, message } from 'alertifyjs'

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
              let request = new XMLHttpRequest();
              request.open('POST', '/token')
              request.onreadystatechange = () => {
                if (request.readyState == 4 && request.status == 200) {
                  let token = JSON.parse(request.response)
                  let decoded = jwt_decode(token['access_token'])
                  User.username = decoded['sub']
                  console.log('authenticated!', decoded)
                  User.token = token['token_type'] + ' ' + token['access_token']
                  User.loggedIn = true
                  success(`${User.username} logged in!`)
                  console.log('User: ', User)
                  m.route.set('/')
                } else if (request.readyState == 4 && request.status != 200) {
                  console.log('error logging in!', request)
                  error('error logging in', 3)
                }
              }
              request.send(form)
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
            }, 'logout')
          ]
        )
      ]
    }
  }
}

export default Login
