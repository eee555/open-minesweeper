import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';

describe('NF IOE efficiency ranking', () => {
    function mountRanking(url: string) {
        const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/ranking', component: RankingApp, children: rankingRoutes }] });
        void router.push(url);
        cy.wrap(router.isReady()).then(() => {
            cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        });
        return router;
    }

    it('switches rankings through the select and keeps sorting, pagination and history in the URL', () => {
        cy.mockPlayerNameFallback();
        const player = { player_id: 42, b: { value: 1, video_id: 8001, timems: 1000 }, i: { value: 0.8, video_id: 8002, timems: 20000 }, e: null };
        cy.intercept('GET', '**/api/effranking/thrp/rank*', { count: 0, players: [] }).as('thrp');
        cy.intercept('GET', '**/api/effranking/nf_ioe/rank*', { count: 21, players: [player] }).as('ioe');
        const router = mountRanking('/ranking/efficiency');
        cy.wait('@thrp');
        cy.get('.efficiency-selector').click();
        cy.get('.el-select-dropdown__item').filter(':visible').contains('NF IOE').click();
        cy.wait('@ioe').its('request.query').should('include', { stat: 'sum', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.path').should('equal', '/ranking/efficiency/nf-ioe');
        cy.get('.nf-ioe-ranking-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.slice(2)).to.deep.equal(['1.000 (1.000)', '0.800', '--', '1.800']);
        });
        cy.get('[data-field=b] .video-preview-link').should('have.attr', 'href', '#/video/8001');
        cy.get('.nf-ioe-pagination .btn-next').click();
        cy.wait('@ioe').its('request.query').should('include', { start: '20', end: '40' });
        cy.get('.nf-ioe-ranking-table thead [data-field=e]').click();
        cy.wait('@ioe').its('request.query').should('include', { stat: 'e', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query').should('deep.equal', { sort: 'e', page: '1', page_size: '20' });
        cy.get('[data-cy=ranking-refresh]').click();
        cy.wait('@ioe');
        cy.get('.efficiency-selector').click();
        cy.get('.el-select-dropdown__item').filter(':visible').contains(i18n.global.t('prop.thrp')).click();
        cy.wait('@thrp');
        cy.then(() => {
            router.back();
        });
        cy.wait('@ioe').its('request.query.stat').should('equal', 'e');
        cy.get('.efficiency-selector').should('contain.text', 'NF IOE');
    });
});
