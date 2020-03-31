import jwt_decode from 'jwt-decode'
import { autoLogin } from './login'

describe('timeline', () => {
  it('opens the timeline editor and loads demo.csv', () => {
    autoLogin()
    cy.visit('http://localhost:8000/#!/projects')
    cy.contains('demo.csv').click()

    cy.url().should('include', '/#!/editor?edl=demo.csv')

    cy.get('#project > tr:nth-child(3)').contains('moon.mp4')

    cy.get('#monitor').should('have.attr', 'src').and('eq', 'videos/train.mp4')

    cy.get('#timeline > .clip:nth-child(2)').should('have.attr', 'description').and('eq', 'moon')
  })
})
