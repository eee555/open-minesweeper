function expectPressedMineControl() {
    cy.get('[data-cy=minigame-mine-down]').should('be.checked');
    cy.get('[data-cy=minigame-mine-down] + .checkbox-button-content').should(($pressed) => {
        // The label is a flex container, so its inline-flex child computes to flex.
        expect($pressed.css('display')).to.equal('flex');
        expect($pressed.css('background-color')).not.to.equal(Cypress.$('[data-cy=minigame-mine-up] + .checkbox-button-content').css('background-color'));
    });
}

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

    it('loads shared game control styles on a direct visit and after reloading', () => {
        cy.visit('/#/minigame/left-click');
        cy.get('[data-cy=minigame-mine-up]').should('be.checked');
        cy.get('[data-cy=minigame-mine-down]').parent('label').click();
        expectPressedMineControl();
        cy.reload();
        expectPressedMineControl();
    });
});
