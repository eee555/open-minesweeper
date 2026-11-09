import { createMemoryHistory, createRouter } from 'vue-router';

import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const token = 'a'.repeat(48);
const nextToken = 'b'.repeat(48);
const requestPath = '**/api/accountlink/saolei/bind/request*';
const confirmPath = '**/api/accountlink/saolei/bind/confirm';
const firstPlayer = { status: 0, uid: 101, username: 'First player' };
const secondPlayer = { status: 0, uid: 202, username: 'Second player' };

function mountBind(value: string | undefined = token) {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/bind/saolei', component: App }] });
    cy.wrap(router.push({ path: '/bind/saolei', query: value === undefined ? {} : { token: value } }));
    cy.mount(App, { global: { plugins: [router, i18n], config: { globalProperties: { $axios } } } });
    return router;
}

describe('Saolei binding authorization', () => {
    it('defaults to syncing, submits an unchecked preference and disables confirmation while sending', () => {
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('GET', requestPath, { body: firstPlayer }).as('request');
        cy.intercept('POST', confirmPath, (req) => gate.then(() => {
            req.reply({ status: 'confirmed', uid: 101, sync: false });
        })).as('confirm');
        mountBind();
        cy.wait('@request');
        cy.get('.bind-intro').should('contain', 'First player').and('contain', '101');
        cy.get('input[type=checkbox]').should('be.checked').uncheck();
        cy.contains('button', 'Confirm').click();
        cy.contains('button', 'Confirm').should('be.disabled').and('have.attr', 'aria-busy', 'true');
        cy.then(() => {
            release();
        });
        cy.wait('@confirm').its('request.body').should('deep.equal', { token, sync: false });
        cy.get('.bind-done').should('contain', 'Linked!');
        cy.get('@confirm.all').should('have.length', 1);
    });

    it('rejects a malformed token without querying the backend', () => {
        cy.intercept('GET', requestPath, { body: firstPlayer }).as('request');
        mountBind('invalid');
        cy.get('.bind-hint').should('contain', 'does not exist or has expired');
        cy.get('button').should('not.exist');
        cy.get('@request.all').should('have.length', 0);
    });

    for (const status of [1, 2]) {
        it(`rejects an inactive remote request with status ${status}`, () => {
            cy.intercept('GET', requestPath, { body: { ...firstPlayer, status } }).as('request');
            mountBind();
            cy.wait('@request');
            cy.get('.bind-hint').should('contain', 'does not exist or has expired');
            cy.get('button').should('not.exist');
        });
    }

    for (const [status, message] of [[403, 'Please log in'], [409, 'already linked'], [502, 'Network error']] as const) {
        it(`shows the confirmation error for HTTP ${status} and allows retry`, () => {
            cy.intercept('GET', requestPath, { body: firstPlayer }).as('request');
            cy.intercept('POST', confirmPath, { statusCode: status, body: {} }).as('failed');
            mountBind();
            cy.wait('@request');
            cy.contains('button', 'Confirm').click();
            cy.wait('@failed');
            cy.get('[role=alert]').should('contain', message);
            cy.contains('button', 'Confirm').should('be.enabled');
            cy.intercept('POST', confirmPath, { body: { status: 'confirmed' } }).as('retry');
            cy.contains('button', 'Confirm').click();
            cy.wait('@retry');
            cy.get('.bind-done').should('contain', 'Linked!');
        });
    }

    it('loads a changed token and ignores the previous request when it arrives later', () => {
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept({ method: 'GET', url: requestPath, query: { token } }, (req) => gate.then(() => {
            req.reply(firstPlayer);
        })).as('first');
        cy.intercept({ method: 'GET', url: requestPath, query: { token: nextToken } }, { body: secondPlayer }).as('second');
        cy.intercept('POST', confirmPath, { body: { status: 'confirmed' } }).as('confirm');
        const router = mountBind();
        cy.get('.bind-hint').should('contain', 'Loading');
        cy.then(() => router.push({ query: { token: nextToken } }));
        cy.wait('@second');
        cy.get('.bind-intro').should('contain', 'Second player');
        cy.then(() => {
            release();
        });
        cy.wait('@first');
        cy.get('.bind-intro').should('contain', 'Second player').and('not.contain', 'First player');
        cy.contains('button', 'Confirm').click();
        cy.wait('@confirm').its('request.body').should('deep.equal', { token: nextToken, sync: true });
    });

    it('ignores a previous confirmation result after navigating to another token', () => {
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept({ method: 'GET', url: requestPath, query: { token } }, { body: firstPlayer }).as('first');
        cy.intercept({ method: 'GET', url: requestPath, query: { token: nextToken } }, { body: secondPlayer }).as('second');
        cy.intercept('POST', confirmPath, (req) => gate.then(() => {
            req.reply({ status: 'confirmed' });
        })).as('confirm');
        const router = mountBind();
        cy.wait('@first');
        cy.get('input[type=checkbox]').uncheck();
        cy.contains('button', 'Confirm').click();
        cy.contains('button', 'Confirm').should('be.disabled');
        cy.then(() => router.push({ query: { token: nextToken } }));
        cy.wait('@second');
        cy.then(() => {
            release();
        });
        cy.wait('@confirm');
        cy.get('.bind-intro').should('contain', 'Second player');
        cy.get('.bind-done').should('not.exist');
        cy.get('input[type=checkbox]').should('be.checked');
        cy.contains('button', 'Confirm').should('be.enabled');
    });
});
