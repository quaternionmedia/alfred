import m from 'mithril'
import jwt_decode from 'jwt-decode'
import { auth } from './Login'

export var User = {
  jwt: null,
  username: null,
  token: null,
  loggedIn: false,
  login: (token) => {
    User.jwt = token
    let decoded = jwt_decode(token['access_token'])
    
    console.log('authenticated!', decoded)
    User.token = token['token_type'] + ' ' + token['access_token']
    auth('/users/me').then(me => {
      User.username = me.first_name
      User.loggedIn = true
      console.log('logged in as: ', User)
      if (m.route.param('redirect')) {
        m.route.set(m.route.param('redirect'))
      } else if (m.route.get() == '/login') {
        m.route.set('/')
      } else {
        m.route.set(m.route.get())
      }
    }, err => {
      console.log('error getting username', err)
    })
    
    // m.redraw()
  },
  logout: () => {
    console.log('logging out', User)
    m.request('/logout', {method: 'post'})
    User.jwt = null
    User.username = null
    User.token = null
    User.loggedIn = false
    window.localStorage.setItem('CREDENTIALS_FLUSH', Date.now().toString())
    window.localStorage.removeItem('CREDENTIALS_FLUSH')
    m.route.set('/')
  }
}
