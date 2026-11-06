import { defineComponent, h, ref } from 'vue';

import App from './App.vue';
import { emptyLinks } from './testFixtures';

import { mockMineracerResponse, mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import { store } from '@/store';
import type { AccountLinksResponse } from '@/utils/accountlinks';

describe('account-link loading and state isolation', () => {
    beforeEach(() => {
        resetAccountLinkStore(1, 1);
    });

    it('does not mark accounts unlinked before loading succeeds, and recovers after a failed initial load', () => {
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('GET', '**/api/accountlink/1', (req) => gate.then(() => {
            req.reply({ statusCode: 503, body: {} });
        })).as('failed');
        mountAccountLink(App, { userId: 1 });
        cy.get('[data-cy=account-details] [role=status]').should('contain', 'Loading');
        cy.get('.account-platform-icon.is-unlinked, [data-cy=account-link-form]').should('not.exist');
        cy.then(() => {
            release();
        });
        cy.wait('@failed');
        cy.get('[data-cy=account-details] [role=alert]').should('contain', 'Could not load linked accounts');
        cy.get('.account-platform-icon.is-unlinked, [data-cy=account-link-form]').should('not.exist');
        cy.closeElNotifications();
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('retry');
        cy.contains('button', 'Retry').click();
        cy.wait('@retry');
        cy.get('[data-cy=account-link-form] input').should('be.enabled');
        cy.get('.account-platform-icon.is-unlinked').should('have.length', 8);
    });

    it('uses Mineracer and Classic detail records even when summary entries are missing', () => {
        const links: AccountLinksResponse = {
            ...emptyLinks,
            m: mockMineracerResponse({ parent: 1 }),
            x: { id: 12345678, parent: 1, update_time: '2026-01-01T00:00:00Z' },
        };
        cy.intercept('GET', '**/api/accountlink/1', { body: links }).as('links');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=m]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=account-details] h2').should('contain', '123456789');
        cy.get('[data-platform=m] .account-platform-icon, [data-platform=x] .account-platform-icon').each(($icon) => {
            cy.wrap($icon).should('have.css', 'opacity', '1');
        });
        cy.get('[data-platform=x]').click();
        cy.get('[data-cy=account-details] h2').should('contain', '12345678');
        cy.get('[data-cy=account-details] input').should('not.exist');
    });

    it('keeps pending submission, failure and retry tied to the submitted platform across tab switches', () => {
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        cy.intercept('POST', '**/api/accountlink/create/', (req) => gate.then(() => {
            req.reply({ statusCode: 503, body: {} });
        })).as('failed');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-cy=account-link-form] input').type('123{enter}');
        cy.get('[data-cy=account-link-form] input').should('be.disabled');
        cy.get('[data-platform=B]').click();
        cy.get('[data-cy=account-link-form] input').type('456');
        cy.get('[data-platform=c]').click();
        cy.get('[data-cy=account-link-form] input').should('be.disabled').and('have.value', '123');
        cy.get('[data-cy=account-link-form]').submit();
        cy.get('[data-platform=B]').click();
        cy.then(() => {
            release();
        });
        cy.wait('@failed');
        cy.get('@failed.all').should('have.length', 1);
        cy.get('[data-cy=account-link-form] input').should('have.value', '456').and('be.enabled');
        cy.get('[data-cy=account-link-form] [role=alert]').should('not.exist');
        cy.closeElNotifications();
        cy.get('[data-platform=c]').click();
        cy.get('[data-cy=account-link-form] [role=alert]').should('be.visible');
        cy.get('[data-cy=account-link-form] input').should('have.value', '123').and('be.enabled');
        cy.intercept('POST', '**/api/accountlink/create/', { body: { id: 1, platform: 'c', identifier: '123', userprofile: 1, verified: false } }).as('retry');
        cy.get('[data-cy=account-link-form] button[type=submit]').click();
        cy.wait('@retry').its('request.body').should('eq', 'platform=c&identifier=123');
        cy.get('[data-cy=account-link-form]').should('not.exist');
        cy.get('[data-platform=B]').click();
        cy.get('[data-cy=account-link-form] input').should('have.value', '456');
    });

    it('ignores an earlier successful private submission after switching the target user', () => {
        const identifier = '18446744073709551615';
        const userId = ref(1);
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('owner');
        cy.intercept('GET', '**/api/accountlink/2', { body: emptyLinks }).as('other');
        cy.intercept('POST', '**/api/accountlink/create/', (req) => gate.then(() => {
            req.reply({ body: { id: 1, platform: 'd', identifier, userprofile: 1, verified: false } });
        })).as('add');
        mountAccountLink(defineComponent({ expose: [], setup: () => () => h(App, { userId: userId.value }) }));
        cy.wait('@owner');
        cy.get('[data-platform=d]').click();
        cy.get('[data-cy=account-link-form] input').type(`${identifier}{enter}`);
        cy.get('[data-cy=account-link-form] input').should('be.disabled');
        cy.then(() => {
            userId.value = 2;
        });
        cy.wait('@other');
        cy.then(() => {
            release();
        });
        cy.wait('@add');
        cy.get('[data-platform=d]').click();
        cy.get('.account-link-main').should('not.contain', identifier);
        cy.get('[data-cy=account-link-form]').should('not.exist');
        cy.contains('Private links are visible only').should('be.visible');
        cy.then(() => {
            userId.value = 1;
        });
        cy.wait('@owner');
        cy.get('[data-platform=d]').click();
        cy.get('[data-cy=account-link-form] input').should('have.value', '');
    });

    for (const isStaff of [false, true]) {
        it(`${isStaff ? 'allows a moderator' : 'does not allow a visitor'} to read private links, without offering to link for another user`, () => {
            resetAccountLinkStore(9, 1);
            store.user.is_staff = isStaff;
            const identifier = '803511102246789123';
            const links: AccountLinksResponse = { ...emptyLinks, summary: [{ id: 1, platform: 'd', identifier, userprofile: 1, verified: true }], d: { id: identifier, parent: 1 } };
            cy.intercept('GET', '**/api/accountlink/1', { body: links }).as('links');
            mountAccountLink(App, { userId: 1 });
            cy.wait('@links');
            cy.get('[data-platform=d]').click();
            cy.get('[data-cy=account-details] h2').should(isStaff ? 'contain' : 'not.contain', identifier);
            if (!isStaff) cy.contains('Private links are visible only').should('be.visible');
            cy.get('[data-cy=account-link-form]').should('not.exist');
            cy.get('[data-platform=q]').click();
            cy.get('[data-cy=account-link-form]').should('not.exist');
        });
    }
});
