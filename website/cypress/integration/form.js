describe('form test', () => {
  it('tests filling out the form', () => {
    cy.visit('localhost:8000/#!/form')

    cy.get('input[name="NAME"]').type("QM")
    cy.get('input[name="LOGO"]').type("qmlogo.png")

    cy.get('textarea[name="ADDRESS"]').type("Earth")

    cy.get('input[name="PHONE"]').type("916.674.2776")
    cy.get('input[name="HOURS"]').type("24 / 7")
    cy.get('input[name="WEBSITE"]').type("quaternion.media")

    cy.get('textarea[name="INITIAL"]').type("Media, in every orientation")
    cy.get('textarea[name="BULLETS"]').type("• Video Production • Application Design • Code Development • 3D Printing • Audio Engineering • Live Music")
    cy.get('textarea[name="OPTIONAL"]').type("Programming & Music")
    // cy.get('textarea[name="MEDIA"]').type("42 mobius loop, \nClouds")
    cy.get('textarea[name="CALL"]').type("What can we create for you?")

    cy.get('input[name="FONT"]').type("Segoe UI Bold")
    cy.get('input[name="DURATION"]').type("10")

  })
})
