/// <reference types="cypress" />
describe('logs in', () => {

  it('fails to access protected resource', () => {
    cy.request({
      url: Cypress.env('HOST') + '/users/me',
      failOnStatusCode: false,
    })
    .its('status')
    .should('equal', 401)
  })

  it('Does not log in with invalid password', () => {
    cy.home()
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

  // it('gets to project page', () => {
  //   cy.visit('/projects')
  //   cy.url().should('eq', '/projects')
  // })
})



//add verify for completed render

//add verify for preview

//add verify for download