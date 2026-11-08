import MediaRanking from './MediaRanking.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<MediaRanking />', () => {
    installHashHistoryCleanup();

    it('renders the author aggregation table and switches the sort metric', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/user-ranking' }, {
            body: {
                items: [{ user_id: 42, hot: 9.87, likes: 12 }],
                total: 1,
                start: 0,
                anchor: '2026-01-01T00:00:00Z',
            },
        }).as('ranking');
        const router = hashRouter({ initialPath: '/ranking/media' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(MediaRanking, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@ranking').its('request.query').should('include', { sort: 'hot', start: '0', count: '20' });
        cy.get('table thead').extractTableData().should((data) => {
            expect(data[0]).to.deep.equal(['#', 'Player', 'Current heat', 'Total likes']);
        });
        cy.get('table tbody').extractTableData().should((data) => {
            expect(data[0]?.[0]).to.equal('1');
            expect(data[0]?.[2]).to.equal('9.87');
            expect(data[0]?.[3]).to.equal('12');
        });
        cy.get('table a[href="#/player/42"]').should('exist');
        cy.contains('button', 'Total likes').click();
        cy.wait('@ranking').its('request.query').should('include', { sort: 'likes' });
    });

    it('renders the empty state', () => {
        cy.intercept({ method: 'GET', pathname: '/api/media/user-ranking' }, {
            body: { items: [], total: 0, start: 0, anchor: '2026-01-01T00:00:00Z' },
        }).as('ranking');
        const router = hashRouter({ initialPath: '/ranking/media' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(MediaRanking, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@ranking');
        cy.get('.base-table-empty').should('have.text', 'No works yet').and('have.attr', 'colspan', '4');
    });
});
