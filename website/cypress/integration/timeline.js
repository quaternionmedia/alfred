import jwt_decode from 'jwt-decode'
import { autoLogin } from './login'

describe('timeline', () => {
  it('opens the timeline editor and loads demo.csv', () => {
    cy.visit('http://api/#!/projects')
    cy.contains('qm').click()

    cy.url().should('include', '/#!/otto?project=qm')
    cy.get('#timeline').find('.clip')
  })
})
