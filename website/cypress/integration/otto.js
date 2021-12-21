/// <reference types="cypress" />
describe('logs in to otto', () => {
  beforeEach(() => {
    cy.loginUI()
    cy.visit('/#!/otto');
  })


    it('clicks the buttons', () => {
    
      cy.get('[title="time selector"]')
      cy.get('[title="trim"]')
      cy.get('[title="move"]')
      cy.get('[title="cut"]')
      cy.get('[title="slip"]')
      cy.get('[title="slide"]')
      cy.get('[title="dual roller"]')
      cy.get('[title="slower"]')
      cy.get('.bar.right > :nth-child(1) > .custom')
      cy.get('[title="faster"]')
      cy.get('[title="save"]')
      cy.get('[title="render"]')
      cy.get('[title="start"]')
      cy.get('[title="back 5s"]')
      cy.get('[title="pause"]')
      cy.get('[title="forward 5s"]')
      cy.get('[title="end"]')
      cy.get('[style="width: auto;"] > :nth-child(1)')
      cy.get('[style="position: absolute; right: 0px;"]')

    })

    it('should move', () => {
      cy.get("div#slider").invoke("attr", "style", "right: 80%;")
      // cy.get('#scale').invoke("val", "1").trigger("change");
      // cy.get('#scale').invoke("val", "10").trigger("change");
      // cy.get('#scale').invoke("val", "100").trigger("change");
    })
})

