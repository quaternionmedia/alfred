const sizes = ['iphone-3', 'iphone-x', 'samsung-s10', 'ipad-2', 'macbook-15']

const allsizes = ['iphone-6', 'ipad-2', 'ipad-2',
'ipad-mini','iphone-3','iphone-4','iphone-5',
'iphone-6','iphone-6+','iphone-x','iphone-xr',
'macbook-11','macbook-13','macbook-15',
'samsung-note9','samsung-s10']

describe('homerescheck', () => {
  sizes.forEach((size) => {
    // make assertions on the logo using
    // an array of different viewports
    it(`Should display menu text on ${size} screen`, () => {
      if (Cypress._.isArray(size)) {
        cy.viewport(size[0], size[1])
      } else {
        cy.viewport(size)
      }

      cy.visit('localhost:8000')
      cy.get(':nth-child(4) > #home-link').should('be.visible')
      cy.get(':nth-child(5) > #projects-link').should('be.visible')
      cy.get(':nth-child(6) > #renders-link').should('be.visible')
      cy.get(':nth-child(7) > #login-link').should('be.visible')
    })
  })
})

describe('ottorescheck', () => {
  sizes.forEach((size) => {
    // make assertions on the logo using
    // an array of different viewports
    it(`Should display play button on ${size} screen`, () => {
      if (Cypress._.isArray(size)) {
        cy.viewport(size[0], size[1])
      } else {
        cy.viewport(size)
      }

      cy.visit('localhost:8000')

      cy.testingLogin()
      cy.wait(100)

      // cy.contains('menu').click()
      cy.get(':nth-child(6) > #projects-link').click()
      cy.contains('tala').click()
      cy.get('[title="start"]').should('be.visible')
    })
  })
})
