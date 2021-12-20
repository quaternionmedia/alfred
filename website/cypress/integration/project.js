describe('project tests', () => {
    beforeEach(() => {
        cy.loginUI()
        cy.projects()
    })

    it('adds new project', () => {
        cy.get('+').should('be.visible')
    })

    // it('finds demo project', () => {
    //     cy.get('.project').contains('qm').should('be.visible')
    // })

    it('finds local projects', () => {
        cy.contains('qm').should('be.visible')
    })

    // it('finds demo project', () => {
    //     cy.contains('Magnussens 2021_2').click()
    //     cy.url().should('eq', Cypress.config().baseUrl + "#!/form?project=Magnussens%202021_2")
    // })

    // it('previews qm project', () => {
    //     cy.contains('Magnussens 2021_2').click()
    //         // cy.url().should('eq', dev.api + "form?project=qm" )
    //     cy.get('[name="preview"]').click()
    //         //add verify for preview
    //     cy.get('.loader')
    //         .should('be.visible')
    //         // .and(($img) => {
    //         //     // "naturalWidth" and "naturalHeight" are set when the image loads
    //         //     expect(
    //         //         $img[0].naturalWidth,
    //         //         'image has natural width'
    //         //     ).to.be.greaterThan(0)
    //         // })
    // })

    // it('preview and renders qm project', () => {
    //     cy.renders()
    //     cy.contains('Magnussens 2021_2').click()
    //     cy.url().should('eq', Cypress.config().baseUrl + "#!/form?project=Magnussens%202021_2")
    //         // cy.get('[name="preview"]').click()
    //         //add verify for preview
    //     cy.get('[name="save"]').click()
    //         //add verify for render
    // })


    // it('goes to render page and checks render complete', () => {
    //     cy.renders()

    //     //add verify for popup
    //     // cy.wait(750)
    //     //add check for number 100
    //     cy.get(':nth-child(2) > :nth-child(7) > p', { 'timeout': 0 }).should('have.value', '')
    // })
})