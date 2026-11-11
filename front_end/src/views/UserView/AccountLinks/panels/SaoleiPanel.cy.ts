import SaoleiPanel from './SaoleiPanel.vue';

import { mockSaoleiImportSummary, mockSaoleiResponse, mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import { store } from '@/store';
import { AccountSaolei } from '@/utils/accountlinks';

describe('<Saolei account panel />', () => {
    beforeEach(() => {
        resetAccountLinkStore(1, 1);
        mockSaoleiImportSummary();
    });

    it('renders the profile and opens the replay list with import controls for the owner', () => {
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [], next_after: null } }).as('savedVideos');
        mountAccountLink(SaoleiPanel, { verified: true, info: new AccountSaolei(mockSaoleiResponse()) });
        cy.wait('@importSummary');
        cy.contains('Saolei Player').should('be.visible');
        cy.get('[data-cy=saolei-auto-sync]').parent().should('have.attr', 'title').and('include', 'update their catalogue daily');
        cy.contains('.description-item', 'Collected replays').should('not.exist');
        cy.get('.account-panel button').filter(':contains("Replay list")').should('have.length', 1).click();
        cy.wait('@savedVideos');
        cy.get('[data-cy=saolei-refresh-full], [data-cy=saolei-refresh-incremental], [data-cy=saolei-import-all]').should('have.length', 3).and('be.enabled');
    });

    it('only offers saved replay browsing on another player account', () => {
        resetAccountLinkStore(2, 1);
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [], next_after: null } }).as('savedVideos');
        mountAccountLink(SaoleiPanel, { verified: true, info: new AccountSaolei(mockSaoleiResponse()) });
        cy.wait('@importSummary');
        cy.get('[data-cy=saolei-auto-sync]').should('not.exist');
        cy.contains('button', 'Refresh profile').should('not.exist');
        cy.contains('button', 'Replay list').click();
        cy.wait('@savedVideos');
        cy.get('[data-cy=saolei-refresh-full], [data-cy=saolei-refresh-incremental], [data-cy=saolei-import-all]').should('not.exist');
    });

    it('grants a moderator the same owner controls on a memorial account', () => {
        resetAccountLinkStore(2, 1);
        store.user.is_staff = true;
        store.player.is_memorial = true;
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [], next_after: null } }).as('savedVideos');
        mountAccountLink(SaoleiPanel, { verified: true, info: new AccountSaolei(mockSaoleiResponse()) });
        cy.wait('@importSummary');
        cy.get('[data-cy=saolei-auto-sync]').should('exist');
        cy.contains('button', 'Refresh profile').should('be.visible');
        cy.contains('button', 'Replay list').click();
        cy.wait('@savedVideos');
        cy.get('[data-cy=saolei-refresh-full], [data-cy=saolei-refresh-incremental], [data-cy=saolei-import-all]').should('have.length', 3).and('be.enabled');
    });

    it('adopts the server value after a successful save, without changing checked while saving', () => {
        const refresh = cy.spy().as('refresh');
        cy.intercept('POST', '**/api/accountlink/saolei/101/settings', { delay: 300, body: mockSaoleiResponse({ auto_sync: false }) }).as('settings');
        mountAccountLink(SaoleiPanel, { verified: true, info: new AccountSaolei(mockSaoleiResponse()), onRefresh: refresh });
        cy.get('[data-cy=saolei-auto-sync]').should('be.checked').parent().click();
        cy.get('[data-cy=saolei-auto-sync]').should('be.checked').and('be.disabled');
        cy.wait('@settings').its('request.body').should('deep.equal', { auto_sync: false });
        cy.get('[data-cy=saolei-auto-sync]').should('not.be.checked').and('not.be.disabled');
        cy.get('@refresh').should('have.been.calledOnce');
    });

    it('preserves the enabled state when saving fails', () => {
        const refresh = cy.spy().as('refresh');
        cy.intercept('POST', '**/api/accountlink/saolei/101/settings', { statusCode: 503, body: {} }).as('settings');
        mountAccountLink(SaoleiPanel, { verified: true, info: new AccountSaolei(mockSaoleiResponse()), onRefresh: refresh });
        cy.get('[data-cy=saolei-auto-sync]').should('be.checked').parent().click();
        cy.wait('@settings');
        cy.get('[data-cy=saolei-auto-sync]').should('be.checked').and('not.be.disabled');
        cy.get('@refresh').should('not.have.been.called');
    });
});
