import GitHubPanel from './GitHubPanel.vue';

import { mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import { AccountGitHub } from '@/utils/accountlinks';

describe('GitHub public ID and profile', () => {
    beforeEach(() => {
        resetAccountLinkStore();
    });

    it('shows the ID without fetching profile data and loads a username only on request', () => {
        cy.intercept('GET', 'https://api.github.com/user/42', { body: { id: 42, login: 'renamed-user' } }).as('profile');
        mountAccountLink(GitHubPanel, { info: new AccountGitHub({ id: '42', parent: 1 }) });
        cy.contains('.description-item', 'GitHub ID').should('contain', '42');
        cy.get('@profile.all').should('have.length', 0);
        cy.contains('button', 'Unlink account').should('not.exist');
        cy.contains('button', 'Load / refresh GitHub profile').click();
        cy.wait('@profile');
        cy.contains('a', 'renamed-user').should('have.attr', 'href', 'https://github.com/renamed-user');
    });

    it('keeps the verified ID visible after a GitHub rate limit and lets the owner unlink', () => {
        cy.intercept('GET', 'https://api.github.com/user/42', { statusCode: 403 }).as('limited');
        cy.intercept('POST', '**/api/accountlink/github/unlink', { statusCode: 200 }).as('unlink');
        cy.on('window:confirm', () => true);
        const refresh = cy.spy().as('refresh');
        mountAccountLink(GitHubPanel, { info: new AccountGitHub({ id: '42', parent: 1 }), owner: true, onRefresh: refresh });
        cy.contains('button', 'Load / refresh GitHub profile').click();
        cy.wait('@limited');
        cy.get('[role=alert]').should('contain', 'does not affect the verified numeric ID');
        cy.contains('.description-item', 'GitHub ID').should('contain', '42');
        cy.contains('button', 'Unlink account').click();
        cy.wait('@unlink');
        cy.get('@refresh').should('have.been.calledOnce');
    });
});
