import { h } from 'vue';
import { RouterView } from 'vue-router';

import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('Tournament ranking navigation', () => {
    installHashHistoryCleanup();

    it('switches four ranking pages with distinct sortable columns and best editions', () => {
        cy.mockPlayerNameFallback();
        const route = rankingRoutes.find((entry) => entry.name === 'ranking_tournament');
        if (!route) throw new Error('Tournament ranking route is missing');
        const router = hashRouter({ routes: [{ ...route, path: '/ranking/tournament' }], initialPath: '/ranking/tournament' });
        const defaultBest = Number('9223372036854775807');
        const row = { user_id: 101, score_current: 10, last_updated: '2099-01-01T00:00:00Z', score_total: 100, gsc_total: 40, gsc_best: 123456007, weekly_total: 30, weekly_classic_total: 30, weekly_classic_best: 34567802612, weekly_nf_total: 0, weekly_nf_best: defaultBest, weekly_qwc_total: 0, weekly_qwc_best: defaultBest, weekly_qwc_nf_total: 0, weekly_qwc_nf_best: defaultBest, weekly_eff_total: 30, weekly_eff_best: 456.123456, weekly_eff_best_year: 2026, weekly_eff_best_week: 13 };
        cy.intercept('GET', '**/api/tournament/user-ranking*', { body: { total: 1, data: [row] } }).as('ranking');
        cy.wrap(router.isReady()).then(() => cy.mount({ render: () => h(RouterView) }, { global: { plugins: [router, i18n], config: { globalProperties: { $axios } } } }));
        cy.wait('@ranking').its('request.query.sort_by').should('equal', 'score_current');
        for (const [kind, sort, best, edition] of [
            ['gsc', 'gsc_total', '123.456', 'GSC#7'],
            ['weekly', 'weekly_total', '345.678', '2026-W12'],
            ['weekly_eff', 'weekly_eff_total', '456.123', '2026-W13'],
        ]) {
            cy.get('select[aria-label="Tournament ranking"]').select(kind);
            cy.wait('@ranking').its('request.query.sort_by').should('equal', sort);
            cy.get('.ranking-table tbody').extractTableData().should((rows) => {
                if (kind === 'weekly') {
                    expect(rows[0]).to.have.length(11);
                    expect(rows[0][4]).to.equal(`${best} (${edition})`);
                } else expect(rows[0].slice(-2)).to.deep.equal([best, edition]);
            });
            cy.wrap(router).its('currentRoute.value.name').should('equal', `ranking_tournament_${kind}`);
        }
    });
});
