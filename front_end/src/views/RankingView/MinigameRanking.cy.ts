import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import type { MinigameRankingGroup } from '@/services/minigameRankingService';
import { pinia } from '@/store/create';
import { trainingGames } from '@/utils/minigame/games';
import { leftClickModes, multiTouchModes } from '@/utils/minigame/leftClickTraining';

const groups: MinigameRankingGroup[] = [
    { game: 'left-click', rankings: leftClickModes.map((mode) => ({ key: mode.rankingKey, game: 'left-click', level: mode.key, density: String(mode.density) as '50' | '75' | '87.5', order: 'asc', unit: 'ms', min_score: 1, max_score: Number.MAX_SAFE_INTEGER, accept_submissions: true })) },
    { game: 'multi-touch', rankings: multiTouchModes.map((mode) => ({ key: mode.rankingKey, game: 'multi-touch', level: mode.key, density: String(mode.density) as '50' | '75' | '87.5', order: 'asc', unit: 'ms', min_score: 1, max_score: Number.MAX_SAFE_INTEGER, accept_submissions: true })) },
    ...(['flag-chord', 'missing-cell'] as const).map((game) => ({ game, rankings: (game === 'flag-chord' ? ['b', 'i'] as const : ['b', 'i', 'e'] as const).map((level) => ({ key: `${game}-${level}-v1`, game, level, density: null, order: 'asc' as const, unit: 'ms' as const, min_score: 1, max_score: Number.MAX_SAFE_INTEGER, accept_submissions: true })) })),
];

function mountRanking(path: string) {
    const router = createRouter({ history: createMemoryHistory(),
        routes: [
            { path: '/ranking', component: RankingApp, children: rankingRoutes },
            ...trainingGames.map((game) => ({ path: `/minigame/${game}`, name: `minigame-${game}`, component: { expose: [], render: () => null } })),
        ] });
    void router.push(path);
    cy.wrap(router.isReady()).then(() => {
        cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
    });
    return router;
}

describe('minigame rankings', () => {
    beforeEach(() => {
        cy.mockPlayerNameFallback();
        cy.intercept('GET', '/api/minigame/rankings', groups).as('rankings');
        cy.intercept({ method: 'GET', pathname: '/api/minigame/*/rank' }, (request) => {
            const game = groups.find((group) => request.url.includes(`/${group.game}/rank`));
            const records = Object.fromEntries(game?.rankings.map((ranking, index) => [ranking.key, index === 1 ? null : { score: 1234, achieved_at: '2026-10-23T00:00:00Z' }]) ?? []);
            request.reply({ count: 25, players: [{ player_id: 42, rank: Number(request.query.start) + 1, records }] });
        }).as('rank');
    });

    it('opens a deep link with nine columns, sorts, paginates, refreshes and switches groups', () => {
        const router = mountRanking('/ranking/minigame/left-click?sort=left-click-e-87.5-v1&page=2');
        cy.wait('@rank').its('request.query').should('include', { sort: 'left-click-e-87.5-v1', start: '20', end: '40' });
        cy.get('.el-tabs__item.is-active').should('have.text', 'Minigames');
        cy.get('[data-cy=minigame-play-link]').should('have.attr', 'href', '/minigame/left-click');
        cy.get('.minigame-ranking-table tbody tr td').should('have.length', 11);
        cy.get('.minigame-ranking-table tbody').should('contain.text', '1.234').and('contain.text', '--');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.attr', 'href', '/minigame/left-click?player=42&key=b-50-v1');
        cy.get('.minigame-ranking-table tbody tr td').eq(3).find('a').should('not.exist');
        cy.get('.minigame-ranking-table [aria-pressed=true]').should('have.attr', 'aria-label', 'Expert 7/8');
        cy.get('[data-cy=minigame-ranking-color]').should('be.disabled');
        cy.get('.minigame-ranking-table [aria-label="Beginner 3/4"]').click();
        cy.wait('@rank').its('request.query').should('include', { sort: 'left-click-b-75-v1', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query.page').should('equal', '1');
        cy.get('.pagination .btn-next').click();
        cy.wait('@rank').its('request.query.start').should('equal', '20');
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@rank');
        for (const [game, label, columns] of [['multi-touch', 'Multi-touch training', 11], ['flag-chord', 'Flag-and-chord training', 4], ['missing-cell', 'Missing cell training', 5]] as const) {
            cy.get('.ranking-selector').click();
            cy.get('.el-select-dropdown__item').contains(label).click();
            cy.wait('@rank').its('request.query.start').should('equal', '0');
            cy.get('.minigame-ranking-table tbody tr td').should('have.length', columns);
            cy.get('[data-cy=minigame-play-link]').should('have.attr', 'href', `/minigame/${game}`);
            cy.get('[data-cy=minigame-replay-link]').first().should('have.attr', 'href', `/minigame/${game}?player=42&key=${game === 'multi-touch' ? 'b-50-v1' : 'b-v1'}`);
        }
        cy.get('[data-cy=minigame-play-link]').click();
        cy.wrap(router).its('currentRoute.value.name').should('equal', 'minigame-missing-cell');
    });

    it('discards a stale response and recovers from a failed refresh', () => {
        const oldRequested = cy.spy().as('oldRequested');
        let release!: () => void;
        const delayed = new Promise<void>((resolve) => {
            release = resolve;
        });
        cy.intercept({ method: 'GET', pathname: '/api/minigame/flag-chord/rank' }, async (request) => {
            if (request.query.sort === 'flag-chord-b-v1') {
                request.alias = 'oldRank';
                oldRequested();
                await delayed;
                request.reply({ count: 99, players: [] });
            } else {
                request.alias = 'newRank';
                request.reply({ count: 0, players: [] });
            }
        });
        const router = mountRanking('/ranking/minigame/flag-chord');
        cy.get('@oldRequested').should('have.been.calledOnce');
        // URL navigation remains available while the old request covers the table with its loading mask.
        cy.then(() => router.push({ query: { sort: 'flag-chord-i-v1' } }));
        cy.wait('@newRank').then(() => {
            release();
        });
        cy.wait('@oldRank');
        cy.get('.pagination').should('contain.text', '0');
        cy.intercept('GET', '**/api/minigame/flag-chord/rank*', { statusCode: 500 }).as('failed');
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@failed');
        cy.get('.el-alert--error').should('be.visible');
        cy.intercept('GET', '**/api/minigame/flag-chord/rank*', { count: 0, players: [] }).as('recovered');
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@recovered');
        cy.get('.el-alert--error').should('not.exist');
    });
});
