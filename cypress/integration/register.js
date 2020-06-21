describe('register', () => {
  it('opens the editor and registers a new user', () => {
    cy.visit('http://localhost:8000/')


    cy.contains('menu').click()
    cy.contains('login').click()
    cy.get('input[name=username]').type('testing')
    cy.get('input[name=password]').type('testing')
    cy.contains('register').click()
    cy.wait(1000)
  })
})
