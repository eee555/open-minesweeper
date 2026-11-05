import PrimeVue from 'primevue/config';

import AccountLink from './AccountLink.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { AccountLinkPlatform } from '@/utils/accountlinks';

describe('staff account-link platform selection', () => {
    it('starts unselected and resets after sending the chosen platform and string identifier', () => {
        const identifier = '18446744073709551615';
        cy.intercept('GET', '/api/accountlink/admin/queue', []).as('queue');
        cy.intercept('POST', '/api/accountlink/verify/', { body: '' }).as('verify');
        cy.mount(AccountLink, { global: { plugins: [i18n, PrimeVue], config: { globalProperties: { $axios } } } });
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
});
