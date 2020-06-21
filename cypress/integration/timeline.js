describe('editor', () => {
  it('opens the editor and loads demo.csv', () => {
    cy.visit('http://localhost:8000/')


    cy.contains('menu').click()
    cy.contains('login').click()
    cy.get('input[name=username]').type('testing')
    cy.get('input[name=password]').type('testing{enter}')

    cy.wait(1000)

    cy.contains('menu').click()
    cy.contains('projects').click()
    cy.wait(100)
    cy.contains('demo').click()

    cy.url().should('include', '/#!/editor?edl=demo.csv')

    cy.get('#project > tr:nth-child(3)').contains('moon.mp4')

    cy.get('#monitor').should('have.attr', 'src').and('eq', 'videos/train.mp4')

    cy.get('#timeline > .clip:nth-child(2)').should('have.attr', 'description').and('eq', 'moon')
  })
})
