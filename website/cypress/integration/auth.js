/// <reference types="cypress" />

// login just once using API
let user

before(function fetchUser() {
  //register user
  cy.request({
    method: 'POST',
    url: '/auth/register',
    body: {
      email: Cypress.env('email'),
      password: Cypress.env('pwd'),
      first_name: Cypress.env('name'),
    },
    failOnStatusCode: false,
  })
  // login
  cy.request({
    method: 'POST',
    url: '/auth/jwt/login',
    body: {
      username: Cypress.env('email'),
      password: Cypress.env('pwd'),
    },
    form: true,
  })
    .its('body')
    .then(res => {
      user = res
    })
})

// but set the user before visiting the page
// so the app thinks it is already authenticated
beforeEach(function setUser() {
  cy.visit('/', {
    onBeforeLoad(win) {
      // and before the page finishes loading
      // set the user object in local storage
      win.localStorage.setItem('user', JSON.stringify(user))
      console.log('yep: ' + win.localStorage.getItem('user'))
    },
  })
  // the page should be opened and the user should be logged in
})

describe('JWT', () => {
  it('makes authenticated request', () => {
    // we can make authenticated request ourselves
    // since we know the token
    cy.request({
      url: '/users/me',
      auth: {
        bearer: user.access_token,
      },
    })
      .its('status')
      .should('equal', 200)
  })
})

describe('authd test', () => {
  it('gets projects', () => {
    cy.request({
      url: '/project',
      auth: {
        bearer: user.access_token,
      },
    }).then(response => {
      expect(response.status).to.eq(200)
      expect(response.body).to.be.an('array')
    })
  })
})
