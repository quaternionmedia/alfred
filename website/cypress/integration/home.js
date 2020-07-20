describe('home', () => {
  it('check home page', () => {
    cy.visit('http://api')
    // cy.testingLogin()

    cy.contains('menu').click()

  })
})
