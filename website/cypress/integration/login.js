/// <reference types="cypress" />
describe('logs in', () => {
  it('using UI', () => {
    cy.visit('/')
    cy.location('pathname').should('equal', '/')
    cy.get(':nth-child(7) > #login-link').click()
    

    // enter valid username and password
    cy.get('[name=username]').type(Cypress.env('email'))
    cy.get('[name=password]').type(Cypress.env('pwd'))
    cy.get('#submit').click()

    // confirm we have logged in successfully
    cy.location('pathname').should('equal', '/')
    cy.get(':nth-child(8) > #login-link')
      .should('be.visible')
      .then(() => {
      /* global window */
        const userString = window.localStorage.getItem('user')
        console.log(userString)

        expect(userString).to.be.a('string')
        const user = JSON.parse(userString)

        expect(user).to.be.an('object')
        expect(user).to.have.keys([
          'access_token',
          'token_type'
        ])

      expect(user.access_token).to.be.a('string')
    })

    // add log out test
  })

  it('fails to access protected resource', () => {
    cy.request({
      url: 'http://localhost:8000/users/me',
      failOnStatusCode: false,
    })
    .its('status')
    .should('equal', 401)
  })

  it('Does not log in with invalid password', () => {
    cy.visit('/')
    cy.location('pathname').should('equal', '/')
    cy.get(':nth-child(7) > #login-link').click()
    // try logging in with invalid password
    cy.get('[name=username]').type('username')
    cy.get('[name=password]').type('wrong-password')
    cy.get('#submit').click()

    // still on /login page plus an error is displayed
    cy.location('pathname').should('equal', '/')
    cy.get('.ajs-message').should('be.visible')
  })

  it('shows menu', () => {
    cy.visit('/')
    cy.get(':nth-child(4) > #home-link').should('be.visible')
    cy.get(':nth-child(5) > #projects-link').should('be.visible')
    cy.get(':nth-child(6) > #renders-link').should('be.visible')
    cy.get(':nth-child(7) > #login-link').should('be.visible')
  })

  // it('gets to project page', () => {
  //   cy.visit('/projects')
  //   cy.url().should('eq', '/projects')
  // })
})



//add verify for completed render

//add verify for preview

//add verify for download