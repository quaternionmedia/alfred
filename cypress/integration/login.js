describe('uilogin', () => {
  it('opens the editor and logs in', () => {
    cy.testingLogin()
  })
})

describe('tokenlogin', () => {
  it('opens the editor and logs in', () => {
    cy.tokenLogin('testing')
  })
})
