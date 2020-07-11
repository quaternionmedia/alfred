describe('home', () => {
  it('check home page', () => {
    cy.testingLogin()
    cy.wait(50)

    cy.contains('menu').click()

    // cy.get('.menu-item')
    //   .find('home')
    //   .should()
  })
})
