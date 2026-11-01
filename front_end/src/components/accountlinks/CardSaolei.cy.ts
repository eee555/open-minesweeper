import CardSaolei from './CardSaolei.vue';
import { mockSaoleiImportSummary, mockSaoleiResponse, mountAccountLink, resetAccountLinkStore } from './testUtils';

import { AccountSaolei } from '@/utils/accountlinks';

describe('<CardSaolei />', () => {
    beforeEach(() => {
        resetAccountLinkStore();
        mockSaoleiImportSummary();
    });

    it('renders saolei account details and import summary', () => {
        mountAccountLink(CardSaolei, {
            id: '101',
            verified: true,
            info: new AccountSaolei(mockSaoleiResponse()),
        });

        cy.contains('Saolei.wang #101');
        cy.contains('Saolei Player');
        cy.wait('@importSummary');
        cy.contains('Collected replays');
        cy.contains('td', '3');
    });

    it('lets the owner turn off automatic sync and open the manual sync window', () => {
        cy.intercept('POST', '**/api/accountlink/saolei/101/settings', { body: mockSaoleiResponse({ auto_sync: false }) }).as('settings');
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [], next_after: null } }).as('savedVideos');
        mountAccountLink(CardSaolei, {
            id: '101', verified: true, info: new AccountSaolei(mockSaoleiResponse()),
        });
        cy.wait('@importSummary');

        cy.get('.p-toolbar .el-link').eq(1).click();
        cy.get('[data-cy=saolei-auto-sync]').should('have.class', 'is-checked').click();
        cy.wait('@settings').its('request.body').should('deep.equal', { auto_sync: false });
        cy.get('[data-cy=saolei-auto-sync]').should('not.have.class', 'is-checked');
        cy.contains('button', 'Manual sync and import').click();
        cy.wait('@savedVideos');
        cy.get('[data-cy=saolei-sync]').should('be.enabled');
    });

    it('only offers saved replay browsing on another player account', () => {
        resetAccountLinkStore(2, 1);
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [], next_after: null } });
        mountAccountLink(CardSaolei, { id: '101', verified: true, info: new AccountSaolei(mockSaoleiResponse()) });
        cy.contains('button', 'Manage').click();
        cy.get('[data-cy=saolei-sync]').should('not.exist');
        cy.get('[data-cy=saolei-auto-sync]').should('not.exist');
        cy.contains('button', 'Refresh profile').should('not.exist');
    });

    it('renders the unverified state', () => {
        mountAccountLink(CardSaolei, {
            id: '101',
            verified: false,
        });

        cy.contains('This account has not been verified.');
        cy.contains('Saolei Player').should('not.exist');
    });
});
