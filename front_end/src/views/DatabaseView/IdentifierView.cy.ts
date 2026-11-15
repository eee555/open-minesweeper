import PrimeVue from 'primevue/config';

import IdentifierView from './IdentifierView.vue';

import { showInvisibleIdentifiers } from '@/components/widgets/identifierDisplay';
import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

function mountQuery(staff = false) {
    store.$reset();
    if (staff) store.login({ id: 2, is_staff: true });
    showInvisibleIdentifiers.value = false;
    cy.mockPlayerNameFallback();
    cy.mount(IdentifierView, {
        global: {
            plugins: [i18n, pinia, PrimeVue, hashRouter()],
            config: { globalProperties: { $axios } },
        },
    });
}

describe('Identifier lookup', () => {
    installHashHistoryCleanup();

    it('finds all identifiers for a player and links to the player profile', () => {
        cy.intercept({ method: 'GET', pathname: '/api/userprofile/identifier', query: { user_id: '42' } }, ['First', 'Second']).as('identifiers');
        mountQuery();
        cy.get('#identifier-player-id').type('42{enter}');
        cy.wait('@identifiers');
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(['First', 'Second']);
        });
        cy.get('table a').should('have.length', 2).first().should('have.attr', 'href', '#/player/42');
        cy.get('[data-cy=identifier-actions]').should('not.exist');
        cy.get('th').should('not.contain.text', 'safe');
    });

    it('distinguishes unbound identifiers from unknown identifiers and clears old results', () => {
        cy.intercept('GET', '/api/identifier/query/exact*', { items: [{ identifier: 'unbound', user_id: null }] }).as('unbound');
        mountQuery();
        cy.get('#identifier-text').type('unbound{enter}');
        cy.wait('@unbound');
        cy.get('table').should('contain.text', 'Unbound');

        cy.intercept('GET', '/api/identifier/query/exact*', { items: [] }).as('unknown');
        cy.get('#identifier-text').clear();
        cy.get('#identifier-text').type('unknown{enter}');
        cy.wait('@unknown');
        cy.get('table').should('contain.text', 'No identifiers found').and('not.contain.text', 'unbound');
    });

    it('requires a positive player ID and reports an empty player result', () => {
        cy.intercept('GET', '/api/userprofile/identifier*', []).as('identifiers');
        mountQuery();
        cy.get('#identifier-player-id').type('0');
        cy.contains('button', 'Find player identifiers').should('be.disabled');
        cy.get('#identifier-player-id').clear();
        cy.get('#identifier-player-id').type('42{enter}');
        cy.wait('@identifiers');
        cy.get('table').should('contain.text', 'No identifiers found');
    });

    it('uses separate APIs for each match mode and case option', () => {
        cy.intercept('GET', '/api/identifier/query/*', { items: [] }).as('matches');
        mountQuery();
        cy.get('#identifier-text').type('Alpha');
        for (const mode of ['exact', 'contains', 'startswith', 'endswith']) {
            cy.get('#identifier-mode').select(mode);
            cy.get('#identifier-ignore-case').uncheck();
            cy.contains('button', 'Find identifier owner').click();
            cy.wait('@matches').then(({ request }) => {
                expect(new URL(request.url).pathname).to.equal(`/api/identifier/query/${mode}`);
                expect(request.query.identifier).to.equal('Alpha');
            });
            cy.get('#identifier-ignore-case').check();
            cy.contains('button', 'Find identifier owner').click();
            cy.wait('@matches').then(({ request }) => {
                expect(new URL(request.url).pathname).to.equal(`/api/identifier/query/i${mode}`);
                expect(request.query.identifier).to.equal('Alpha');
            });
        }
    });

    it('keeps a single regex API and preserves the case checkbox preference', () => {
        cy.intercept('GET', '/api/identifier/query/regex*', { items: [{ identifier: 'Alpha', user_id: null }] }).as('matches');
        mountQuery();
        cy.get('#identifier-ignore-case').check();
        cy.get('#identifier-mode').select('regex');
        cy.get('#identifier-ignore-case').should('not.exist');
        cy.get('#identifier-text').type('(?i)^alpha{enter}');
        cy.wait('@matches').its('request.query.identifier').should('eq', '(?i)^alpha');
        cy.get('table').should('contain.text', 'Alpha');
        cy.get('#identifier-mode').select('exact');
        cy.get('#identifier-ignore-case').should('be.checked');
    });

    it('paginates, sorts and filters owners locally after one query', () => {
        const items = Array.from({ length: 53 }, (_, index) => ({
            identifier: `Alpha${String(index).padStart(2, '0')}`,
            user_id: index % 3 === 0 ? 42 : index % 3 === 1 ? 43 : null,
        }));
        cy.intercept('GET', '/api/identifier/query/contains*', { items: items.toReversed() }).as('matches');
        mountQuery();
        cy.get('#identifier-mode').select('contains');
        cy.get('#identifier-text').type('Alpha{enter}');
        cy.wait('@matches').its('request.query').should('deep.equal', { identifier: 'Alpha' });
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.slice(0, 25).map((item) => item.identifier));
        });
        cy.get('.p-paginator-next').click();
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.slice(25, 50).map((item) => item.identifier));
        });
        cy.contains('th', 'Identifier / pattern').click();
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.toReversed().slice(0, 25).map((item) => item.identifier));
        });
        cy.get('.p-datatable-thead > tr').should('have.length', 1);
        cy.contains('th', 'Owner').find('button[aria-label="Filter owner"]').click();
        cy.get('[data-cy=filter-owner] input[aria-label="Player #42"]').parent().click();
        cy.realPress('Escape');
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.toReversed().filter((item) => item.user_id === 42).map((item) => item.identifier));
        });
        cy.contains('th', 'Owner').find('button[aria-label="Filter owner"]').click();
        cy.get('[data-cy=filter-owner] input[aria-label="Unbound"]').parent().click();
        cy.realPress('Escape');
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.toReversed().filter((item) => item.user_id !== 43).slice(0, 25).map((item) => item.identifier));
        });
        cy.contains('th', 'Owner').find('button[aria-label="Filter owner"]').click();
        cy.contains('[role="dialog"] button', 'Clear').click();
        cy.get('table').getTable().should((rows) => {
            expect(rows.map((row) => row['Identifier / pattern'])).to.deep.equal(items.toReversed().slice(0, 25).map((item) => item.identifier));
        });
        cy.get('@matches.all').should('have.length', 1);

        cy.contains('th', 'Owner').find('button[aria-label="Filter owner"]').click();
        cy.get('[data-cy=filter-owner] input[aria-label="Unbound"]').parent().click();
        cy.realPress('Escape');
        cy.get('table').getTable().should('have.length', 17);
        cy.get('#identifier-text').clear();
        cy.get('#identifier-text').type('Alpha{enter}');
        cy.wait('@matches');
        cy.contains('th', 'Owner').find('button[aria-label="Filter owner"]').click();
        cy.get('[data-cy=filter-owner]').should('be.visible');
        cy.get('[data-cy=filter-owner] input:checked').should('not.exist');
        cy.realPress('Escape');
        cy.get('table').getTable().should('have.length', 25);
        cy.get('.p-paginator-page-selected').should('have.text', '1');
    });

    it('rejects overly broad queries, clears previous results and allows a narrower retry', () => {
        cy.intercept('GET', '/api/identifier/query/contains*', {
            items: [{ identifier: 'Alpha', user_id: null }],
        }).as('matches');
        mountQuery();
        cy.get('#identifier-mode').select('contains');
        cy.get('#identifier-text').type('Alpha{enter}');
        cy.wait('@matches');
        cy.get('table').should('contain.text', 'Alpha');

        cy.intercept('GET', '/api/identifier/query/contains*', {
            statusCode: 400,
            body: { code: 'too_many_matches', detail: 'Identifier query matches more than 1000 results. Please narrow your search.' },
        }).as('tooBroad');
        cy.get('#identifier-text').clear();
        cy.get('#identifier-text').type('A{enter}');
        cy.wait('@tooBroad');
        cy.get('[role="alert"]').should('be.visible').and('contain.text', 'More than 1000 identifiers match. Please narrow your search');
        cy.get('table').should('not.exist');
        cy.get('#identifier-text').should('be.enabled');

        cy.intercept('GET', '/api/identifier/query/contains*', { items: [{ identifier: 'Alpha1', user_id: null }] }).as('narrower');
        cy.get('#identifier-text').clear();
        cy.get('#identifier-text').type('Alpha1{enter}');
        cy.wait('@narrower');
        cy.get('[role="alert"]').should('not.exist');
        cy.get('table').should('contain.text', 'Alpha1');
    });

    it('reports a rate limit and enables retry', () => {
        cy.intercept('GET', '/api/identifier/query/exact*', { statusCode: 429, body: { detail: 'Rate limit exceeded' } }).as('limited');
        mountQuery();
        cy.get('#identifier-text').type('Alpha{enter}');
        cy.wait('@limited');
        cy.contains('Too many requests').should('be.visible');
        cy.closeElNotifications();
        cy.get('#identifier-text').should('be.enabled');
        cy.contains('button', 'Find identifier owner').should('be.enabled');
        cy.get('table').should('not.exist');
    });

    it('reveals invisible characters while copying and querying the original string', () => {
        const identifier = ' 玩家 & +\u200B ';
        cy.intercept({ method: 'GET', pathname: '/api/identifier/query/exact', query: { identifier } }, {
            items: [{ identifier, user_id: 42 }],
        }).as('owner');
        mountQuery();
        cy.window().then((win) => {
            const copy = cy.stub(win.navigator.clipboard, 'writeText').as('copy');
            copy.resolves();
        });
        cy.contains('label', 'Show invisible characters').find('input').check();
        cy.get('#identifier-text').type(`${identifier}{enter}`);
        cy.wait('@owner');
        cy.get('.identifier-text').should('have.text', '␠玩家␠&␠+⟦U+200B⟧␠');
        cy.get('table a').should('have.attr', 'href', '#/player/42');
        cy.get('#identifier-text').should('have.value', identifier);
        cy.get('button[aria-label="Copy"]').click();
        cy.get('@copy').should('have.been.calledOnceWith', identifier);
        cy.closeElNotifications();
    });

    it('lets staff review, bind and unbind an identifier through row actions', () => {
        const identifier = 'Review & +';
        cy.intercept('GET', '/api/identifier/query/exact*', { items: [{ identifier, user_id: null, safe: false }] }).as('matches');
        cy.intercept('POST', '/api/identifier/safe', { body: { identifier, user_id: null, safe: true } }).as('approve');
        cy.intercept('POST', '/api/identifier/bind', { body: { identifier, user_id: 42, safe: true } }).as('bind');
        mountQuery(true);
        cy.get('#identifier-text').type(`${identifier}{enter}`);
        cy.wait('@matches');
        cy.get('table').getTable().its('0.safe').should('eq', 'false');
        cy.get('[data-cy=identifier-actions]').click();
        cy.contains('.identifier-actions button', 'Bind user').should('be.disabled');
        cy.contains('.identifier-actions button', 'Set safe = true').click();
        cy.wait('@approve').then(({ request }) => {
            const body = new URLSearchParams(request.body as string);
            expect(body.get('identifier')).to.equal(identifier);
            expect(body.get('safe')).to.equal('true');
        });
        cy.get('table').getTable().its('0.safe').should('eq', 'true');

        cy.get('[data-cy=identifier-actions]').click();
        cy.contains('.identifier-actions button', 'Bind user').click();
        cy.get('#identifier-bind-user').clear();
        cy.get('#identifier-bind-user').type('-1');
        cy.contains('[role=dialog]:visible button', 'Save').should('be.disabled');
        cy.get('#identifier-bind-user').clear();
        cy.get('#identifier-bind-user').type('42');
        cy.contains('[role=dialog]:visible button', 'Save').click();
        cy.wait('@bind').then(({ request }) => {
            const body = new URLSearchParams(request.body as string);
            expect(body.get('identifier')).to.equal(identifier);
            expect(body.get('id')).to.equal('42');
        });
        cy.get('[role=dialog]:visible').should('not.exist');
        cy.get('table a').should('have.attr', 'href', '#/player/42');

        cy.get('@bind.all').should('have.length', 1);
        cy.intercept('POST', '/api/identifier/bind', { body: { identifier, user_id: null, safe: true } }).as('unbind');
        cy.get('[data-cy=identifier-actions]').click();
        cy.contains('.identifier-actions button', 'Set safe = false').should('be.disabled');
        cy.contains('.identifier-actions', 'Enter 0 in Bind user').should('be.visible');
        cy.contains('.identifier-actions button', 'Bind user').click();
        cy.get('#identifier-bind-user').should('be.visible').and('have.value', '42');
        cy.get('#identifier-bind-user').clear();
        cy.get('#identifier-bind-user').type('0');
        cy.contains('[role=dialog]:visible button', 'Save').click();
        cy.wait('@unbind').then(({ request }) => {
            const body = new URLSearchParams(request.body as string);
            expect(body.get('identifier')).to.equal(identifier);
            expect(body.get('id')).to.equal('0');
        });
        cy.get('[role=dialog]:visible').should('not.exist');
        cy.get('table').should('contain.text', 'Unbound').and('contain.text', identifier);
        cy.get('@approve.all').should('have.length', 1);
        cy.intercept('POST', '/api/identifier/safe', { body: { identifier, user_id: null, safe: false } }).as('unsafe');
        cy.get('[data-cy=identifier-actions]').click();
        cy.contains('.identifier-actions button', 'Set safe = false').click();
        cy.wait('@unsafe').then(({ request }) => {
            const body = new URLSearchParams(request.body as string);
            expect(body.get('identifier')).to.equal(identifier);
            expect(body.get('safe')).to.equal('false');
        });
        cy.get('table').getTable().its('0.safe').should('eq', 'false');
        cy.get('@matches.all').should('have.length', 1);
        cy.get('@unbind.all').should('have.length', 1);
        cy.get('@unsafe.all').should('have.length', 1);
    });

    it('includes safe for staff player lookups and keeps a failed mutation unchanged', () => {
        cy.intercept('GET', '/api/identifier/query/user/42', { items: [{ identifier: 'Owned', user_id: 42, safe: true }] }).as('identifiers');
        cy.intercept('POST', '/api/identifier/bind', { statusCode: 404, body: { detail: 'User not found' } }).as('failedBind');
        mountQuery(true);
        cy.get('#identifier-player-id').type('42{enter}');
        cy.wait('@identifiers');
        cy.get('table').getTable().its('0.safe').should('eq', 'true');
        cy.get('[data-cy=identifier-actions]').click();
        cy.contains('.identifier-actions button', 'Bind user').click();
        cy.get('#identifier-bind-user').clear();
        cy.get('#identifier-bind-user').type('999999');
        cy.contains('[role=dialog]:visible button', 'Save').click();
        cy.wait('@failedBind');
        cy.contains('User not found').should('be.visible');
        cy.get('[role=dialog]:visible').should('be.visible');
        cy.get('table a').should('have.attr', 'href', '#/player/42');
        cy.closeElNotifications();
    });
});
