import tinycolor from 'tinycolor2';
import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import { colorTheme } from '@/store';
import { colorThemes } from '@/store/color';
import { pinia } from '@/store/create';
import { local } from '@/store/local';

describe('Thrp efficiency ranking', () => {
    const originalColored = local.value.colored;
    const originalIOE = colorTheme.value.ioe;
    afterEach(() => {
        local.value.colored = originalColored;
        colorTheme.value.ioe = originalIOE;
    });

    function mountRanking(url = '/ranking/efficiency') {
        const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/ranking', component: RankingApp, children: rankingRoutes }] });
        void router.push(url);
        cy.wrap(router.isReady()).then(() => {
            cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        });
        return router;
    }

    it('renders all levels, colors sum by sum/3 and keeps sort and pagination in the URL', () => {
        local.value.colored = true;
        colorTheme.value.ioe = { thresholds: [1], colors: ['#224466', '#ffee00'] };
        cy.mockPlayerNameFallback();
        const player = { player_id: 42, b: { value: 1.5, video_id: 8001, upload_time: '2026-10-19T12:00:00Z' }, i: null, e: { value: 0.9, video_id: 8002, upload_time: '2026-10-19T12:01:00Z' }, e_nf: { value: 1, video_ids: [8003, 8004, 8005] } };
        cy.intercept({ method: 'GET', pathname: '/api/effranking/thrp/rank' }, { count: 21, players: [player] }).as('ranking');
        const router = mountRanking();
        cy.wait('@ranking').its('request.query').should('include', { stat: 'sum', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.path').should('equal', '/ranking/efficiency/thrp');
        cy.get('.el-tabs__item.is-active').should('have.text', 'Efficiency');
        cy.get('.thrp-ranking-table tbody tr').should('have.length', 1);
        cy.get('.thrp-ranking-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.slice(2)).to.deep.equal(['1.500', '--', '0.900', '2.400', '1 x 3']);
        });
        cy.get('.thrp-ranking-table tbody [data-field=b] a').should('have.attr', 'href', '#/video/8001');
        cy.get('.thrp-ranking-table tbody [data-field=sum] a').should('not.exist');
        cy.get('.thrp-ranking-table tbody [data-field=b]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(1.5)).toRgbString());
        cy.get('.thrp-ranking-table tbody [data-field=sum]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(0.8)).toRgbString());
        cy.get('[data-cy=ranking-color]').click();
        cy.get('.thrp-ranking-table tbody [data-field=sum]').should(($cell) => {
            expect($cell[0].style.backgroundColor).to.equal('');
        });
        cy.get('.thrp-pagination .btn-next').click();
        cy.wait('@ranking').its('request.query').should('include', { start: '20', end: '40' });
        cy.get('.thrp-ranking-table thead [data-field=e]').click();
        cy.wait('@ranking').its('request.query').should('include', { stat: 'e', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query').should('deep.equal', { sort: 'e', page: '1', page_size: '20' });
        cy.get('[data-cy=ranking-refresh]').click();
        cy.wait('@ranking');
        cy.get('.thrp-ranking-table thead [data-field=e_nf]').click();
        cy.wait('@ranking').its('request.query').should('include', { stat: 'e_nf', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query.sort').should('equal', 'e_nf');
    });

    it('opens a deep link and retries a failed request before displaying an empty table', () => {
        cy.intercept('GET', '**/api/effranking/thrp/rank*', { statusCode: 500 }).as('failed');
        mountRanking('/ranking/efficiency/thrp?sort=i&page_size=50');
        cy.wait('@failed').its('request.query').should('include', { stat: 'i', start: '0', end: '50' });
        cy.get('[role=alert]').should('contain.text', 'Unable to load ranking');
        cy.intercept('GET', '**/api/effranking/thrp/rank*', { count: 0, players: [] }).as('retry');
        cy.get('[data-cy=ranking-refresh]').click();
        cy.wait('@retry');
        cy.get('[role=alert]').should('not.exist');
        cy.get('.base-table-empty').should('have.attr', 'colspan', '7');
        cy.get('.thrp-ranking-table thead [data-field=i]').should('have.attr', 'aria-pressed', 'true');
    });
});
