describe('alfred', () => {
  it('opens the editor and loads demo', () => {
    cy.testingLogin()
    cy.wait(50)

    // cy.contains('menu').click()
    // cy.wait(50)

    cy.get(':nth-child(6) > #projects-link').click()
    cy.wait(50)

    cy.contains('demo').click()
    cy.wait(500)

    cy.sliderInteract('#slider',1)
    cy.wait(50)
    // cy.get('#sider').invoke('val', 5).trigger('change');

    cy.get('[title="move"]')
    cy.get('[name="videos/train.mp4"]').move({ x: 100, y: 100 })
    // cy.sliderInteract('#scale',75)
    // cy.sliderInteract('#scale',50)
    // cy.sliderInteract('#scale',10)
  })
})
