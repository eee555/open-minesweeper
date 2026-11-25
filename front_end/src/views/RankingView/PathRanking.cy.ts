import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { mockVideoInfo } from '@cy/support/videoInfo';

describe('Path efficiency ranking', () => {
    it('renders four groups and keeps sorting, pagination and shared refresh connected to the API', () => {
        cy.mockPlayerNameFallback();
        mockVideoInfo([{ id: 8001, software: 'e' }]);
        const player = {
            player_id: 42,
            b_path: { value: 0, video_id: 8001 },
            b_cpath: null,
            b_epath: null,
            i_path: { value: 160, video_id: 8001 },
            i_cpath: null,
            i_epath: null,
            e_path: { value: 197.5308624, video_id: 8001 },
            e_cpath: null,
            e_epath: null,
        };
        cy.intercept('GET', '**/api/effranking/path/rank*', { count: 200, players: [player] }).as('ranking');
        const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/ranking', component: RankingApp, children: rankingRoutes }] });
        void router.push('/ranking/efficiency/path');
        cy.wrap(router.isReady()).then(() => {
            cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        });
        cy.wait('@ranking').its('request.query').should('include', { stat: 'sum_epath', start: '0', end: '20' });
        cy.get('.path-ranking-table th[scope=colgroup]').should('have.length', 4);
        cy.get('.path-ranking-table tbody').extractTableData().should((rows) => {
            expect(rows.map((row) => row.slice(-3))).to.deep.equal([['22.346', '--', '--']]);
        });
        cy.get('.path-ranking [data-cy=jump]').clear();
        cy.get('.path-ranking [data-cy=jump]').type('27{enter}');
        cy.wait('@ranking').its('request.query').should('include', { start: '26', end: '46' });
        cy.get('.path-ranking-table thead [data-field=b_path]').click();
        cy.wait('@ranking').its('request.query').should('include', { stat: 'b_path', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query').should('deep.equal', { sort: 'b_path', start: '1', page_size: '20' });
        cy.get('.path-ranking [data-cy=page-size]').select('50');
        cy.wait('@ranking').its('request.query').should('include', { stat: 'b_path', start: '0', end: '50' });
        cy.get('[data-cy=ranking-refresh]').click();
        cy.wait('@ranking');
    });
});
