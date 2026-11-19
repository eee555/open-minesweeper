import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';

describe('Efficiency rankings', () => {
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
        cy.get('.efficiency-selector').should('have.value', 'thrp').select('nf_ioe');
        cy.wait('@ioe').its('request.query').should('include', { stat: 'sum', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.path').should('equal', '/ranking/efficiency/nf-ioe');
        cy.get('.efficiency-selector').should('have.value', 'nf_ioe');
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
        cy.get('.efficiency-selector').select('thrp');
        cy.wait('@thrp');
        cy.then(() => {
            router.back();
        });
        cy.wait('@ioe').its('request.query.stat').should('equal', 'e');
        cy.get('.efficiency-selector').should('have.value', 'nf_ioe');
        cy.intercept('GET', '**/api/effranking/tpe/rank*', {
            count: 1, players: [{ player_id: 42, i: { value: 0, video_id: 8001 }, i2: { value: 1, video_id: 8003 }, i3: { value: 2, video_id: 8004 }, e: { value: 123.456789, video_id: 8002 }, e2: { value: 200, video_id: 8005 }, e3: { value: 300, video_id: 8006 } }],
        }).as('tpe');
        cy.get('.efficiency-selector').select('tpe');
        cy.wait('@tpe').its('request.query').should('include', { stat: 'sum', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.path').should('equal', '/ranking/efficiency/tpe');
        cy.get('.tpe-ranking-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.slice(2)).to.deep.equal(['0.000', '1.000', '2.000', '123.457', '200.000', '300.000', '123.457', '201.000', '302.000']);
        });
        cy.get('.tpe-ranking-table th[scope=colgroup]').should('have.length', 3).and('have.attr', 'colspan', '3');
        cy.get('.tpe-ranking-table tbody [data-field=e]').should('have.attr', 'title', '123.456789');
        cy.get('.tpe-ranking-table [data-field=i] .video-preview-link').should('have.attr', 'href', '#/video/8001');
        cy.get('.tpe-ranking-table [data-field=sum] a').should('not.exist');
        cy.get('.tpe-ranking-table thead [data-field=e3]').click();
        cy.wait('@tpe').its('request.query.stat').should('equal', 'e3');
        cy.get('.tpe-ranking-table th[aria-sort=ascending]').should('contain.text', 'TPE3');
    });
});
