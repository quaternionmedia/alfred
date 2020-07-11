import m from 'mithril'
import jwt_decode from 'jwt-decode'

export var User = {
  jwt: null,
  username: null,
  token: null,
  loggedIn: false,
  login: (token) => {
    User.jwt = token
    let decoded = jwt_decode(token['access_token'])
    User.username = decoded['sub']
    console.log('authenticated!', decoded)
    User.token = token['token_type'] + ' ' + token['access_token']
    User.loggedIn = true
    console.log('logged in as: ', User)
    if (m.route.param('redirect')) {
      m.route.set(m.route.param('redirect'))
    } else {
      m.route.set(m.route.get())
    }
    m.redraw()
  },
  logout: () => {
    console.log('logging out', User)
    User.jwt = null
    User.username = null
    User.token = null
    User.loggedIn = false
    window.localStorage.setItem('CREDENTIALS_FLUSH', Date.now().toString())
    window.localStorage.removeItem('CREDENTIALS_FLUSH')
    m.redraw()
  }
}
