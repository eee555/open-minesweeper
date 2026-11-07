import App from './App.vue';
import { emptyLinks } from './testFixtures';

import { mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';

describe('GitHub account-link entry', () => {
    beforeEach(() => {
        resetAccountLinkStore(1, 1);
    });

    it('uses OAuth instead of accepting a manually entered ID and permits retry after start failure', () => {
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        cy.intercept('POST', '**/api/accountlink/github/start', { statusCode: 503, body: { object: 'github', category: 'not_configured' } }).as('start');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=g]').click();
        cy.get('[data-cy=account-details] input').should('not.exist');
        cy.contains('button', 'Link with GitHub').click();
        cy.wait('@start');
        cy.get('[data-cy=github-link] [role=alert]').should('contain', 'Could not start authorization');
        cy.contains('button', 'Link with GitHub').should('be.enabled');
    });

    it('shows a guest the public numeric ID without owner actions or automatic profile requests', () => {
        resetAccountLinkStore(2, 1);
        cy.intercept('GET', '**/api/accountlink/1', { body: {
            ...emptyLinks,
            g: { id: '123456789', parent: 1 },
            summary: [{ id: 1, platform: 'g', identifier: '123456789', userprofile: 1, verified: true }],
        } }).as('links');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=g]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=account-details] h2').should('contain', '#123456789');
        cy.contains('button', 'Unlink account').should('not.exist');
        cy.contains('button', 'Link with GitHub').should('not.exist');
    });

    it('cancels the returned authorization when the user has switched away before start completes', () => {
        const state = 's'.repeat(43);
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        cy.intercept('POST', '**/api/accountlink/github/start', (request) => gate.then(() => {
            request.reply({ body: { authorization_url: `https://github.com/login/oauth/authorize?state=${state}` } });
        })).as('start');
        cy.intercept('POST', '**/api/accountlink/github/cancel', { statusCode: 200 }).as('cancel');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=g]').click();
        cy.contains('button', 'Link with GitHub').click();
        cy.get('[data-platform=B]').click();
        cy.then(() => {
            release();
        });
        cy.wait('@start');
        cy.wait('@cancel').its('request.body').should('deep.equal', { state });
        cy.get('[data-platform=B]').should('have.attr', 'aria-pressed', 'true');
    });
});
