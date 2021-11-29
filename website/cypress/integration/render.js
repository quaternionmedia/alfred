

describe('qm render', () => {
    it('preview and renders qm project', () => {
        cy.visit('/#!/login')
        cy.get('input[name=username]').type(Cypress.env('email'))
        cy.get('input[name=password]').type(Cypress.env('pwd'))
        cy.get('#submit').click()
          cy.visit("/#!/projects")
          cy.contains('Magnussens 2021_2').click()
          cy.url().should('eq', Cypress.config().baseUrl + "#!/form?project=Magnussens%202021_2" )
          // cy.get('[name="preview"]').click()
          //add verify for preview
          cy.get('[name="save"]').click()
          //add verify for render
        })
    })

describe('qm preview', () => {
    it('goes to render page and checks render complete', () => {
        cy.visit('/#!/login')
        cy.get('input[name=username]').type(Cypress.env('email'))
        cy.get('input[name=password]').type(Cypress.env('pwd'))
        cy.get('#submit').click()
          cy.visit('/#!/renders')
          cy.url().should('eq', Cypress.config().baseUrl + '#!/renders' )
          //add verify for popup
          cy.wait(750)
          //add check for number 100
          cy.get(':nth-child(2) > :nth-child(7) > p', {'timeout':0}).should('have.value', '')
      })
    })