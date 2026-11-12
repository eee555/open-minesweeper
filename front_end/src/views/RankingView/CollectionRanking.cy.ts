import CollectionRanking from './CollectionRanking.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const records = {
    collection: {
        'std:sum:count': 3,
        'std:sum:probability': 0.012345,
        'std:sum:asb': 1.23456,
        'nf:sum:count': 2,
        'nf:sum:probability': 0.12345,
        'nf:sum:asb': 2.5,
    },
};

describe('<CollectionRanking />', () => {
    installHashHistoryCleanup();

    it('loads the default sort, switches NF and sort columns through the URL', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/rank' }, {
            body: { count: 21, rows: [{ player_id: 42, records }] },
        }).as('ranking');
        const router = hashRouter({ initialPath: '/ranking/speed/collection' });
        cy.mount(CollectionRanking, { props: { colored: true }, global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        cy.wait('@ranking').its('request.query').should('include', { ranking: 'collection', field: 'std:sum:count', start: '0', end: '20' });
        cy.get('.derived-ranking-table thead th').should('have.length', 18);
        cy.get('.derived-ranking-table thead th[rowspan="2"]').should('have.length', 2);
        cy.get('.derived-ranking-table thead th[scope="colgroup"][colspan="3"]').should('have.length', 4);
        cy.get('.derived-ranking-table tbody [data-field="collection:sum:count"]').should('have.text', '3');
        cy.get('.derived-ranking-table tbody [data-field="collection:sum:probability"]').should('have.text', '1.23%');
        cy.get('.derived-ranking-table tbody [data-field="collection:sum:asb"]').should('have.text', '1.235').and('have.attr', 'title', '1.23456');
        cy.get('[data-cy=derived-nf]').check();
        cy.wait('@ranking').its('request.query').should('include', { field: 'nf:sum:count', start: '0' });
        cy.get('.derived-ranking-table thead [data-field="collection:e:asb"]').click();
        cy.wait('@ranking').its('request.query').should('include', { field: 'nf:e:asb' });
        cy.wrap(router).its('currentRoute.value.query').should('include', { sort: 'collection:e:asb', nf: '1', page: '1' });
        cy.get('.derived-pagination .btn-next').click();
        cy.wait('@ranking').its('request.query').should('include', { start: '20', end: '40' });
    });
});
