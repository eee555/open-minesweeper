import AccountLink from './AccountLink.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { AccountLinkPlatform } from '@/utils/accountlinks';
import type { AccountLinkQueuePageResponse, AccountLinkQueueResponse } from '@/utils/accountlinks/common';

const emptyQueue: AccountLinkQueuePageResponse = { count: 0, page: 1, page_size: 10, items: [] };

function mountAccountLink() {
    cy.mount(AccountLink, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
}

describe('staff account-link platform selection', () => {
    it('starts unselected and resets after sending the chosen platform and string identifier', () => {
        const identifier = '18446744073709551615';
        cy.intercept({ method: 'GET', pathname: '/api/accountlink/admin/queue' }, emptyQueue).as('queue');
        cy.intercept('POST', '/api/accountlink/verify/', { body: '' }).as('verify');
        mountAccountLink();
        cy.wait('@queue');
        cy.get('select[aria-label="Platform"]').should('have.prop', 'value', '');
        cy.get('select[aria-label="Platform"]').should('have.prop', 'selectedIndex', 0);
        cy.get('.el-form input[type=number]').clear();
        cy.get('.el-form input[type=number]').type('42');
        cy.get('select[aria-label="Platform"]').select(AccountLinkPlatform.Discord);
        cy.contains('.el-form-item__label', 'Platform ID').next().find('input').type(identifier);
        cy.contains('.el-form button', 'Link').click();
        cy.wait('@verify').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ id: '42', platform: AccountLinkPlatform.Discord, identifier });
        });
        cy.wait('@queue');
        cy.get('select[aria-label="Platform"]').should('have.prop', 'value', '');
        cy.get('select[aria-label="Platform"]').should('have.prop', 'selectedIndex', 0);
        cy.contains('.el-form-item__label', 'Platform ID').next().find('input').should('have.value', '');
        cy.get('@queue.all').should('have.length', 2);
    });

    it('requests a backend page and refreshes on sort, filter and pagination changes', () => {
        const items: AccountLinkQueueResponse[] = Array.from({ length: 10 }, (_, index) => ({
            id: index + 1, platform: AccountLinkPlatform.Discord, identifier: `id-${index}`, userprofile: 42, verified: false,
        }));
        cy.intercept({ method: 'GET', pathname: '/api/accountlink/admin/queue' }, { count: 12, page: 1, page_size: 10, items }).as('queue');
        mountAccountLink();
        cy.wait('@queue').its('request.query').should('include', { page: '1', page_size: '10', order: '' });
        cy.get('[data-cy=account-link-table] tbody tr').should('have.length', 10);
        cy.get('[data-cy=sort-user-id]').click();
        cy.wait('@queue').its('request.query').should('include', { page: '1', order: 'asc' });
        cy.get('[data-cy=filter-platform]').select(AccountLinkPlatform.Discord);
        cy.wait('@queue').its('request.query').should('include', { page: '1', platform: AccountLinkPlatform.Discord });
        cy.get('[data-cy=account-link-pagination] [data-cy=next]').click();
        cy.wait('@queue').its('request.query').should('include', { page: '2' });
        cy.get('@queue.all').should('have.length', 4);
    });
});
