describe('editor', () => {
  it('opens the editor and loads demo.csv', () => {
    cy.testingLogin()

    cy.wait(1000)

    cy.contains('menu').click()
    cy.contains('projects').click()
    cy.wait(100)
    cy.contains('demo').click()

    // cy.url().should('include', '/#!/editor?edl=demo.csv')

    // cy.get('#project > tr:nth-child(3)').contains('moon.mp4')
    //
    // cy.get('#monitor').should('have.attr', 'src').and('eq', 'videos/train.mp4')
    //
    // cy.get('#timeline > .clip:nth-child(2)').should('have.attr', 'description').and('eq', 'moon')
  })
})
