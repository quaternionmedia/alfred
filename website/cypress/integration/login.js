const username = 'johndoe'
const password = 'secret'

describe('the login page', () => {
  it('sets auth header when logging in for server authentication', () => {
    cy.visit('http://localhost:8000/')
    cy.contains('menu').click()
    cy.contains('login').click()
    cy.url().should('include', '/#!/login')
    cy.contains('menu').click()
    cy.contains('projects').click()
    cy.url().should('include', '/#!/login')
    autoLogin()
    cy.get(':nth-child(6) > #projects-link').click()
    cy.contains('demo.csv')
  })
})

export function autoLogin() {
  cy.visit('http://localhost:8000/#!/login')
  cy.get('input[name=username]').type(username)
  cy.get('input[name=password]').type(`${password}{enter}`)
  cy.url().should('eq', 'http://localhost:8000/#!/')
}
