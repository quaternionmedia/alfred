describe('the home page', () => {
  it('loads the home page', () => {
    goHome()
  })
})

export function goHome() {
    cy.visit('/')
    cy.url().should('eq', Cypress.config().baseUrl)
}
