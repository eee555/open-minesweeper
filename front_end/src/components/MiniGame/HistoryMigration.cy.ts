import HistoryMigration from './HistoryMigration.vue';

import i18n from '@/i18n';

describe('minigame history migration notice', () => {
    it('shows migration progress, blocks dismissal and closes when migration finishes or fails', () => {
        cy.mount(HistoryMigration, { props: { progress: null }, global: { plugins: [i18n] } });
        cy.get('[data-cy=minigame-history-migration]').should('not.exist');
        cy.get<ComponentWrapper<typeof HistoryMigration>>('@vue').then((wrapper) => wrapper.setProps({ progress: { completed: 0, total: 10 } }));
        cy.get('[data-cy=minigame-history-migration]').should('be.visible').and('contain', 'Optimizing replay format. Please do not close this page.');
        cy.get('[data-cy=minigame-history-migration]').should('have.attr', 'open');
        cy.get('[data-cy=minigame-history-migration] progress').should('have.attr', 'value', '0').and('have.attr', 'max', '10');
        cy.realPress('Escape');
        cy.get('[data-cy=minigame-history-migration]').should('be.visible').and('have.attr', 'open');
        // Also block repeated close requests without another user activation.
        cy.realPress('Escape');
        cy.get('[data-cy=minigame-history-migration]').should('be.visible').and('have.attr', 'open');
        cy.get<ComponentWrapper<typeof HistoryMigration>>('@vue').then((wrapper) => wrapper.setProps({ progress: { completed: 6, total: 10 } }));
        cy.get('[data-cy=minigame-history-migration] progress').should('have.attr', 'value', '6');
        cy.get('[data-cy=minigame-history-migration] output').should('have.text', '6 / 10');
        cy.get<ComponentWrapper<typeof HistoryMigration>>('@vue').then((wrapper) => wrapper.setProps({ progress: null }));
        cy.get('[data-cy=minigame-history-migration]').should('not.exist');
    });
});
