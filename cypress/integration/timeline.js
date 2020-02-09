describe('timeline', () => {
  it('opens the timeline and loads test.csv', () => {
    cy.visit('http://localhost:8000/')
    cy.contains('menu').click()
    cy.contains('projects').click()
    cy.contains('test.csv').click()
    cy.url().should('include', '/#!/timeline?edl=test.csv')
  })
})
