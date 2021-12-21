// Thanks to 
// https://github.com/qaboxletstest/Cypress-Demo/blob/master/cypress/integration/QABOX/TC_02_Window.spec.js

describe('Window Test Suite Commands', () => {

    beforeEach(() => {
        cy.loginUI();
    });

    it('Window Test Commands - URI Properties', () => {
        cy.window().should(win => {
            const loc = win.location
            expect(loc.hash).to.eql('#!/');
            expect(loc.host).to.eql(cy.location().host);
            expect(loc.pathname).to.eql('/');
            expect(loc.protocol).to.eql('http:');
        })
    });

    it('Window Test Commands - Page Reload', () => {
        cy.window().should(win => {
            win.location.reload()
        })
    });

    it('Window Test Commands - Page Navigation', () => {
        // cy.contains('home').click()
        cy.window().should(win => {
            win.history.back() // win.history.go(-1)
        })
        cy.get(':nth-child(7) > #login-link').should('be.visible')
        cy.window().should(win => {
            win.history.forward() // win.history.go(1)
        })
        cy.get(':nth-child(6) > #projects-link').should('be.visible')
        cy.get(':nth-child(7) > #renders-link').should('be.visible')
    });

    it('Window Test Commands - Storage', () => {
        cy.window().should(win => {
            expect(win.localStorage.length).to.eql(1);
            win.localStorage.setItem('Name', 'alfredTestBox')
            expect(win.localStorage.getItem('Name')).to.eql('alfredTestBox');
        })
    });

    it('Window Test Commands - Storage', () => {
        cy.clearLocalStorage()
    });

    it('Document Test Commands - Get Width & Height', () => {
        cy.document().should(doc => {
            const docObj = Cypress.$(doc)
            let docHeight =  docObj.height()
            let docWidht =  docObj.width()
            console.log(`Screen Height is ${docHeight}`)
            console.log(`Screen Width is ${docWidht}`)
            Cypress.$(doc.body).css('background-color', 'purple')
        })
    });
});