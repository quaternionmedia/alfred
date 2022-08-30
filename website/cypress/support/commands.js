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
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })

Cypress.Commands.add('home', () => {
  cy.visit('/')
  cy.url().should('eq', Cypress.config().baseUrl)
})

Cypress.Commands.add('renders', () => {
  cy.visit('/#!/renders')
  cy.url().should('eq', Cypress.config().baseUrl + '#!/renders')
})

Cypress.Commands.add('projects', () => {
  cy.visit('/#!/projects')
  cy.url().should('eq', Cypress.config().baseUrl + '#!/projects')
})

Cypress.Commands.add(
  'loginApi',
  (username = Cypress.env('email'), password = Cypress.env('pwd')) => {
    return cy.request({
      method: 'POST',
      url: '/auth/jwt/login',
      body: {
        username: Cypress.env('email'),
        password: Cypress.env('pwd'),
      },
      form: true,
    })
  }
)

Cypress.Commands.add('loginUI', () => {
  cy.home()
  cy.location('pathname').should('equal', '/')
  cy.get('#login-link').click({ force: true })

  // enter valid username and password
  cy.get('[name=username]').type(Cypress.env('email'))
  cy.get('[name=password]').type(Cypress.env('pwd'))
  cy.get('#submit').click({ force: true })

  // confirm we have logged in successfully
  cy.location('pathname').should('equal', '/')
})

Cypress.Commands.add('logout', () => {
  cy.visit('/#!/logout')
})
