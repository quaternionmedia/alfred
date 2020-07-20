const username = 'johndoe'
const password = 'secret'

describe('the login page', () => {
  it('sets auth header when logging in for server authentication', () => {
    cy.visit('http://api/')
    cy.contains('menu').click()
    cy.contains('login').click()
    cy.url().should('include', '/#!/login')
    cy.contains('menu').click()
    cy.contains('renders').click()
    cy.url().should('include', '/#!/login')
    autoLogin()
    cy.url().should('include', 'http://api/#!/')
  })
})

export function autoLogin() {
  cy.visit('http://api/#!/login')
  cy.get('input[name=username]').type(username)
  cy.get('input[name=password]').type(`${password}{enter}`)
}
