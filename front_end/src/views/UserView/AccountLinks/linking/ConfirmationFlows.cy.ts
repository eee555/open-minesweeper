import App from '../App.vue';
import { emptyLinks } from '../testFixtures';

import { mockMineracerAccountLinkSessionResponse, mockMineracerResponse, mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import type { ClassicAccountLinkResponse } from '@/utils/accountlinks';

describe('account-link confirmation flows', () => {
    beforeEach(() => {
        resetAccountLinkStore(1, 1);
        cy.clock(Date.now(), ['setTimeout', 'clearTimeout']);
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
    });

    it('validates Classic UID, retains a rejected draft, retries and refreshes accounts once after confirmation', () => {
        const none: ClassicAccountLinkResponse = { status: 'none', uid: null, request_id: null, expires_at: null, error_category: '' };
        const pending: ClassicAccountLinkResponse = { ...none, status: 'pending', uid: 12345678, request_id: 1, expires_at: new Date(Date.now() + 60000).toISOString() };
        cy.intercept('GET', '**/api/accountlink/classic/status/', { body: none }).as('status');
        cy.intercept('POST', '**/api/accountlink/classic/start/', { statusCode: 409, body: { object: 'classic', category: 'identifier_conflict' } }).as('rejected');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=x]').click();
        cy.wait('@status');
        cy.get('.classic-form input').type('1234567');
        cy.get('.classic-form button').should('be.disabled');
        cy.get('.classic-form input').clear();
        cy.get('.classic-form input').type('01234567');
        cy.get('.classic-form button').should('be.disabled');
        cy.get('.classic-form input').clear();
        cy.get('.classic-form input').type('12345678{enter}');
        cy.wait('@rejected').its('request.body').should('eq', 'uid=12345678');
        cy.get('.classic-link [role=status]').should('contain', 'This UID is already linked');
        cy.get('.classic-form input').should('have.value', '12345678');
        cy.intercept('POST', '**/api/accountlink/classic/start/', { body: pending }).as('started');
        cy.get('.classic-form button').click();
        cy.wait('@started');
        cy.get('.classic-form').should('not.exist');
        cy.contains('Confirm the request inside the mini game').should('be.visible');
        cy.intercept('GET', '**/api/accountlink/classic/status/', { body: { ...pending, status: 'allow' } }).as('confirmed');
        cy.intercept('GET', '**/api/accountlink/1', { body: { ...emptyLinks, x: { id: 12345678, parent: 1, update_time: new Date().toISOString() } } }).as('linked');
        cy.tick(5000);
        cy.wait('@confirmed');
        cy.wait('@linked');
        cy.get('[data-cy=account-details] h2').should('contain', '12345678');
        cy.get('.classic-link').should('not.exist');
        cy.tick(15000);
        cy.get('@confirmed.all').should('have.length', 1);
        cy.get('@linked.all').should('have.length', 1);
    });

    it('retains a Mineracer session created while another platform is selected, retries an expired session and refreshes once on confirmation', () => {
        const pending = mockMineracerAccountLinkSessionResponse({ expires_at: new Date(Date.now() + 60000).toISOString(), next_poll_at: null });
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('POST', '**/api/accountlink/mineracer/start/', (req) => gate.then(() => {
            req.reply({ body: pending });
        })).as('start');
        cy.intercept('GET', `**/api/accountlink/mineracer/status/${pending.session_id}`, { body: pending }).as('status');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=m]').click();
        cy.contains('button', 'Generate link').click();
        cy.contains('button', 'Generate link').should('be.disabled');
        cy.get('[data-platform=B]').click();
        cy.get('[data-cy=account-link-form] input').type('456');
        cy.then(() => {
            release();
        });
        cy.wait('@start');
        cy.tick(6000);
        cy.get('@status.all').should('have.length', 0);
        cy.get('[data-platform=m]').click();
        cy.wait('@status');
        cy.contains('a', 'Open link').should('have.attr', 'href', pending.verification_uri_complete);
        cy.get('@start.all').should('have.length', 1);
        cy.intercept('GET', `**/api/accountlink/mineracer/status/${pending.session_id}`, { body: { ...pending, status: 'expired' } }).as('expired');
        cy.contains('button', 'Refresh status').click();
        cy.wait('@expired');
        cy.contains('.mineracer-link [role=status]', 'The link has expired').should('be.visible');
        cy.contains('a', 'Open link').should('not.exist');
        const retry = { ...pending, session_id: 'retry-session', verification_uri_complete: 'https://mineracer.com/link?code=RETRY' };
        cy.intercept('POST', '**/api/accountlink/mineracer/start/', { body: retry }).as('retry');
        cy.contains('button', 'Generate new link').click();
        cy.wait('@retry');
        cy.contains('a', 'Open link').should('have.attr', 'href', retry.verification_uri_complete);
        cy.intercept('GET', '**/api/accountlink/mineracer/status/retry-session', { body: { ...retry, status: 'confirmed', remote_userid: '123456789' } }).as('confirmed');
        cy.intercept('GET', '**/api/accountlink/1', { body: { ...emptyLinks, m: mockMineracerResponse({ parent: 1 }) } }).as('linked');
        cy.contains('button', 'Refresh status').click();
        cy.wait('@confirmed');
        cy.wait('@linked');
        cy.get('[data-cy=account-details] h2').should('contain', '123456789');
        cy.tick(10000);
        cy.get('@confirmed.all').should('have.length', 1);
        cy.get('@linked.all').should('have.length', 1);
        cy.get('[data-platform=B]').click();
        cy.get('[data-cy=account-link-form] input').should('have.value', '456');
    });
});
