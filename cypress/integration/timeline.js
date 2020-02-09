describe('timeline', () => {
  it('opens the timeline and loads test.csv', () => {
    cy.visit('http://localhost:8000/')
    cy.contains('menu').click()
    cy.contains('projects').click()
    cy.contains('test.csv').click()

    cy.url().should('include', '/#!/timeline?edl=test.csv')

    cy.get('#project > tr:nth-child(2)').contains('BigBuckBunny')

    cy.get('#monitor').should('have.attr', 'src').and('eq', 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4')

    cy.get('#timeline > .clip:nth-child(1)').should('have.attr', 'description').and('eq', 'clip 1')
  })
})
