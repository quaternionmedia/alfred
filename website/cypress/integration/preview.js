
describe('qm preview', () => {
    it('previews qm project', () => {
            cy.visit('/#!/login')
            cy.get('input[name=username]').type(Cypress.env('email'))
            cy.get('input[name=password]').type(Cypress.env('pwd'))
            cy.get('#submit').click()
            // cy.url().should('eq', dev.api + 'login')
            cy.visit("/#!/projects")
            cy.contains('Magnussens 2021_2').click()
            // cy.url().should('eq', dev.api + "form?project=qm" )
            cy.get('[name="preview"]').click()
          //add verify for preview
          cy.get('.loader')
          .should('be.visible')
        //   .and(($img) => {
        //     // "naturalWidth" and "naturalHeight" are set when the image loads
        //     expect(
        //       $img[0].naturalWidth,
        //       'image has natural width'
        //     ).to.be.greaterThan(0)
        //   })
        })
    })