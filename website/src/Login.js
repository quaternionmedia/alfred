import m from 'mithril'
import { Menu } from './Menu'
import { User } from './User'
import jwt_decode from 'jwt-decode'

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
                  m.route.set('/')
                } else if (request.readyState == 4 && request.status != 200) {
                  console.log('error logging in!', request)
                }
              }
              request.send(form)
              // .then((e) => {
              // })
              // m.request({
              //   url: '/token',
              //   method: 'POST',
              //   serialize: m.route.buildQueryString,
              //   headers: {
              //     'X-Requested-With': 'XMLHttpRequest',
              //     'Content-Type':'application/x-www-form-urlencoded',
              //   },
              //   // config: function(xhr) {
              //   //   xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest')
              //   //   xhr.setRequestHeader('Content-Type','application/x-www-form-urlencoded')
              //   // },
              //   // data: {
              //   //   username: document.getElementById('username').value,
              //   //   password: document.getElementById('password').value,
              //   // },
              //   data: form,
              // }).then((res) => {
              //   console.log('authenticated!', res)
              //   if (res['token']) {
              //     User.token = res['type'] + ' ' + res['token']
              //   }
              // })
            }},
          ),
          ]
        )
      ]
    }
  }
}

export default Login
