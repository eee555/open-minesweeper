import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const rankingBody = { items: [], total: 0, start: 0, anchor: new Date().toISOString() };
const meBody = { balance: 5, likes_sent: 0, banned: false };

describe('<WorksView />', () => {
    installHashHistoryCleanup();

    it('keeps submit and refresh above the table without any tab bar', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, { body: rankingBody }).as('ranking');
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, { body: meBody }).as('me');
        const router = hashRouter({ initialPath: '/works' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(App, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@ranking');
        cy.get('.base-table').should('exist');
        cy.get('.el-tabs').should('not.exist');
        cy.get('[data-sort=pending]').should('not.exist');
        cy.get('[data-cy=open-submit]').should('be.visible');
        cy.get('[data-cy=refresh-works]').should('be.visible').click();
        cy.wait('@ranking');
        cy.get('[data-cy=open-submit]').click();
        cy.get('.el-dialog:visible [data-cy=submit-format]').should('have.value', 'B_v');
    });
});
