import { defineComponent, h, KeepAlive, nextTick, ref } from 'vue';

import App from './App.vue';
import { emptyLinks } from './testFixtures';

import { mockAccountLinksResponse, mockSaoleiImportSummary, mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import { store } from '@/store';
import type { AccountLinksResponse } from '@/utils/accountlinks';

describe('<AccountLinks page />', () => {
    beforeEach(() => {
        resetAccountLinkStore(1, 1);
        mockSaoleiImportSummary();
    });

    it('shows all platforms, selects one bordered tile and preserves platform drafts without another aggregate request', () => {
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('.account-platform-grid button').should('have.length', 9);
        cy.get('.account-platform-grid button').should(($buttons) => {
            expect(Array.from($buttons, (button) => button.dataset.platform)).to.deep.equal(['c', 'a', 'w', 'B', 'm', 'x', 'g', 'q', 'd']);
        });
        cy.get('.account-platform-icon').should('have.css', 'opacity', '0.5');
        cy.get('[data-platform=c]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=account-details]').should('have.length', 1);
        cy.get('[data-cy=account-link-form] input').type('123');
        cy.get('[data-platform=B]').click();
        cy.get('[data-cy=account-link-form] input').type('456');
        cy.get('[data-platform=c]').focus();
        cy.realPress('Enter');
        cy.get('[data-cy=account-link-form] input').should('have.value', '123');
        cy.get('[aria-pressed=true].account-platform-button').should('have.length', 1);
        cy.get('@links.all').should('have.length', 1);
    });

    it('displays a single complete platform panel and keeps the selection after a successful profile refresh', () => {
        cy.intercept('GET', '**/api/accountlink/1', { body: mockAccountLinksResponse() }).as('links');
        cy.intercept('POST', '**/accountlink/update/', { body: { type: 'success' } }).as('update');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=w]').click();
        cy.get('[data-cy=account-details] > .account-panel').should('have.length', 1);
        cy.contains('Total 3BV').should('be.visible');
        cy.contains('button', 'Synchronize').click();
        cy.wait('@update');
        cy.wait('@links');
        cy.get('[data-platform=w]').should('have.attr', 'aria-pressed', 'true');
        cy.contains('Total 3BV').should('be.visible');
    });

    it('submits each platform-specific form to its matching platform using Enter', () => {
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        for (const [index, platform] of ['c', 'a', 'w', 'B', 'q', 'd'].entries()) {
            const identifier = platform === 'd' ? '18446744073709551615' : '123';
            cy.intercept('POST', '**/api/accountlink/create/', { body: { id: index + 1, platform, identifier, userprofile: 1, verified: false } }).as(`add${platform}`);
            cy.get(`[data-platform=${platform}]`).click();
            cy.get(`[data-platform=${platform}] .account-platform-icon`).should('have.css', 'opacity', '0.5');
            cy.get('[data-cy=account-link-form] input').type(`${identifier}{enter}`);
            cy.wait(`@add${platform}`).its('request.body').should('eq', `platform=${platform}&identifier=${identifier}`);
            cy.get('[data-cy=account-details] h2').should('contain', identifier);
            cy.contains('This account has not been verified.').should('be.visible');
            cy.get(`[data-platform=${platform}] .account-platform-icon`).should('have.css', 'opacity', '1');
            cy.get('[data-cy=account-link-form]').should('not.exist');
        }
    });

    it('clears private information and ignores an older response after logout', () => {
        const privateLinks: AccountLinksResponse = { ...emptyLinks, summary: [{ id: 8, platform: 'd', identifier: '803511102246789123', userprofile: 1, verified: true }], d: { id: '803511102246789123', parent: 1 } };
        cy.intercept('GET', '**/api/accountlink/1', { body: privateLinks, delay: 400 }).as('owner');
        mountAccountLink(App, { userId: 1 });
        cy.get('@owner.all').should('have.length', 1);
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('guest');
        cy.then(() => {
            store.logout();
        });
        cy.wait('@guest');
        cy.wait('@owner');
        cy.get('[data-platform=d]').click();
        cy.get('.account-link-main').should('not.contain', '803511102246789123');
        cy.get('[data-cy=account-link-form]').should('not.exist');
        cy.contains('Private links are visible only').should('be.visible');
        cy.get('[data-platform=d] .account-platform-icon, [data-platform=q] .account-platform-icon').each(($icon) => {
            cy.wrap($icon).should('have.css', 'opacity', '1');
        });
        cy.get('.account-platform-grid button').should('have.length', 9);
    });

    it('stops Classic polling when switching away and restores it on return', () => {
        cy.clock(Date.now(), ['setTimeout', 'clearTimeout']);
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        cy.intercept('GET', '**/api/accountlink/classic/status/', { body: { status: 'pending', uid: 12345678, request_id: 1, expires_at: '2030-01-01T00:00:00Z', error_category: '' } }).as('classic');
        mountAccountLink(App, { userId: 1 });
        cy.wait('@links');
        cy.get('[data-platform=x]').click();
        cy.wait('@classic');
        cy.get('[data-platform=c]').click();
        cy.tick(6000);
        cy.get('@classic.all').should('have.length', 1);
        cy.get('[data-platform=x]').click();
        cy.wait('@classic');
        cy.get('@classic.all').should('have.length', 2);
    });

    it('unmounts the active platform when the kept-alive user tab is deactivated', () => {
        cy.clock(Date.now(), ['setTimeout', 'clearTimeout']);
        cy.intercept('GET', '**/api/accountlink/1', { body: emptyLinks }).as('links');
        cy.intercept('GET', '**/api/accountlink/classic/status/', { body: { status: 'pending', uid: 12345678, request_id: 1, expires_at: '2030-01-01T00:00:00Z', error_category: '' } }).as('classic');
        const visible = ref(true);
        mountAccountLink(defineComponent({ expose: [], setup: () => () => h(KeepAlive, null, { default: () => (visible.value ? h(App, { userId: 1 }) : null) }) }));
        cy.wait('@links');
        cy.get('[data-platform=x]').click();
        cy.wait('@classic');
        cy.then(async () => {
            visible.value = false;
            await nextTick();
        });
        cy.get('.account-link-main').should('not.exist');
        cy.tick(6000);
        cy.get('@classic.all').should('have.length', 1);
        cy.then(async () => {
            visible.value = true;
            await nextTick();
        });
        cy.get('.account-link-main').should('exist');
        cy.wait('@links');
        cy.get('[data-platform=c]').should('have.attr', 'aria-pressed', 'true');
    });
});
