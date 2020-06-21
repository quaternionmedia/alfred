describe('login', () => {
  it('opens the editor and logs in', () => {
    cy.visit('http://localhost:8000/')


    cy.contains('menu').click()
    cy.contains('login').click()
    cy.get('input[name=username]').type('testing')
    cy.get('input[name=password]').type('testing{enter}')
  })
})
