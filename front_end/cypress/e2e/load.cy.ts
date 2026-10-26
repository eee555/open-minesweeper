describe('Main navigation', () => {
    it('menu navigation', () => {
        cy.visit('/');
        cy.get('#app[data-v-app]', { timeout: Cypress.config('pageLoadTimeout') }).should('be.visible');
        cy.url().should('match', /\/#\/$/);
        cy.get('[data-cy=app-header] [data-navigation-id=ranking] a').click();
        cy.url().should('include', '/#/ranking');
        cy.get('[data-cy=app-header] [data-navigation-id=database] a').click();
        cy.url().should('match', /\/#\/database\/users$/);
        cy.contains('.el-tabs__item', '标识查询').click();
        cy.url().should('match', /\/#\/database\/identifiers$/);
        cy.visit('/#/video');
        cy.url().should('match', /\/#\/database\/videos$/);
        cy.get('[data-cy=app-header] [data-navigation-id=settings] a').click();
        cy.url().should('match', /\/#\/settings$/);
    });
});
