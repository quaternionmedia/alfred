describe('form test', () => {
  it('tests filling out the form', () => {
    cy.visit('http://api')
    cy.contains('menu').click()
    cy.contains('form').click()
    cy.get('input[name="name"]').type("QM")
    cy.get('#logo').type("qmlogo.png")

    cy.get('textarea[name="address"]').type("Earth")

    cy.get('input[name="phone"]').type("916.674.2776")
    cy.get('input[name="hours"]').type("24 / 7")
    cy.get('input[name="website"]').type("quaternion.media")

    cy.get('textarea[name="initial"]').type("Media, in every orientation")
    cy.get('textarea[name="bullets"]').type("• Video Production • Application Design • Code Development • 3D Printing • Audio Engineering • Live Music")
    cy.get('textarea[name="optional"]').type("Programming & Music")
    // cy.get('textarea[name="MEDIA"]').type("42 mobius loop, \nClouds")
    cy.get('textarea[name="call"]').type("What can we create for you?")

    cy.get('input[name="font"]').type("Segoe UI Bold")
    cy.get('input[name="duration"]').type("10")

  })
})
