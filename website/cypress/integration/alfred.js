describe('alfred', () => {
  it('opens the editor and loads demo', () => {
    cy.testingLogin()
    cy.wait(50)

    cy.contains('menu').click()
    cy.wait(50)

    cy.contains('projects').click()
    cy.wait(50)

    cy.contains('demo').click()
    cy.wait(50)

    cy.get('[title="time selector"]').click()
    cy.wait(50)

    cy.get('#timeline').children().click({ multiple: true })

    // cy.sliderInteract('#slider',1)
    // cy.wait(50)
    // cy.get('#sider').invoke('val', 5).trigger('change');

    cy.get('[title="move"]').click()
    cy.wait(50)
    //
    cy.get('[name="videos/TheGreatTrainRobbery-300k.mp4"]')
    .trigger('mousedown', { which: 1, pageX: 600, pageY: 100 }).debug()
    .trigger('mousemove', { which: 1, pageX: 600, pageY: 600 })
    .trigger('mouseup')

    // cy.get('[name="videos/TheGreatTrainRobbery-300k.mp4"]')
    //     .trigger('mousedown', { which: 1 })
    //     .trigger('mousemove', { clientX: 0, clientY: -400 })
    //     .trigger('mouseup', {force: true})
    // cy.sliderInteract('#scale',75)
    // cy.sliderInteract('#scale',50)
    // cy.sliderInteract('#scale',10)
  })
})
