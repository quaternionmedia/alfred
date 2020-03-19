
export var User = {
  username: null,
  token: null,
  loggedIn: false,
  logout: () => {
    console.log('logging out', User)
    User.username = null
    User.token = null
    User.loggedIn = false
  }
}
