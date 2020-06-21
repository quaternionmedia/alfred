describe('render', () => {
  it('opens the editor and loads then renderes the otto demo', () => {
    cy.visit('http://localhost:8000/')


    cy.contains('menu').click()
    cy.contains('login').click()
    cy.get('input[name=username]').type('testing')
    cy.get('input[name=password]').type('testing{enter}')

    cy.wait(1000)

    cy.contains('menu').click()
    cy.contains('projects').click()

    cy.wait(100)

    cy.contains('tala').click()

    cy.get('.i').contains('render').click()
  })
})
