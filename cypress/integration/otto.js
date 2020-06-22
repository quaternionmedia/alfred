describe('otto', () => {
  it('opens the editor and loads otto demo', () => {
    cy.testingLogin()

    cy.wait(100)

    cy.contains('menu').click()
    cy.contains('projects').click()

    cy.contains('tala').click()

    cy.get('div.clip').click({ multiple: true })

    // cy.url().should('include', '/#!/editor?edl=demo')
    //
    // cy.get('#project > tr:nth-child(3)').contains('moon.mp4')
    //
    // cy.get('#monitor').should('have.attr', 'src').and('eq', 'videos/train.mp4')
    //
    // cy.get('#timeline > .clip:nth-child(2)').should('have.attr', 'description').and('eq', 'moon')
  })
})
