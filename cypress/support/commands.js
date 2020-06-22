// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... })

Cypress.Commands.add('clickLink', (label) => {
  cy.get('a').contains(label).click()
})

Cypress.Commands.add('downloadFile', (url, directory, fileName) => {
  return cy.getCookies().then((cookies) => {
    return cy.task('downloadFile', {
      url,
      directory,
      cookies,
      fileName,
    })
  })
})

Cypress.Commands.add('getSessionStorage', (key) => {
  cy.window().then((window) => window.sessionStorage.getItem(key))
})

Cypress.Commands.add('setSessionStorage', (key, value) => {
  cy.window().then((window) => {
    window.sessionStorage.setItem(key, value)
  })
})

Cypress.Commands.add('typeLogin', (user) => {
  cy.get('#username')
    .type(user.name)

  cy.get('input[name=password]')
    .type(user.password+'{enter}')
})

Cypress.Commands.add('testingLogin', () => {
  cy.visit('http://localhost:8000/')
  cy.contains('menu').click()
  cy.contains('login').click()
  cy.typeLogin({name:'testing',password: 'testing'})
})

Cypress.Commands.add('tokenLogin', (user) => {
  cy.request({
    method: 'POST',
    url: '/token',
    body: {
      username: 'testing',
      password: 'testing'
    }
  }).then((resp) => {
    cy.request({
      method: 'POST',
      url: '/',
      headers: ({ Authorization: 'Bearer ' + resp.body.token })
    })
  })
})

Cypress.Commands.add('createUserUI', () => {
  cy.visit('http://localhost:8000/')
  cy.contains('menu').click()
  cy.contains('login').click()
  cy.get('input[name=username]').type('testing')
  cy.get('input[name=password]').type('testing')
  cy.contains('register').click()
})


Cypress.Commands.add('createUser', (user) => {
  cy.request({
    method: 'POST',
    url: 'https://www.example.com/tokens',
    body: {
      email: 'admin_username',
      password: 'admin_password'
    }
  }).then((resp) => {
    cy.request({
      method: 'POST',
      url: 'https://www.example.com/users',
      headers: ({ Authorization: 'Bearer ' + resp.body.token }),
      body: user
    })
  })
})
