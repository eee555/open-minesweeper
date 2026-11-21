import tinycolor from 'tinycolor2';
import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import RankingApp from './App.vue';
import { rankingRoutes } from './routes';

import $axios from '@/http';
import i18n from '@/i18n';
import type { MinigameRankingGroup } from '@/services/minigameRankingService';
import { colorThemes } from '@/store/color';
import { pinia } from '@/store/create';
import { local } from '@/store/local';
import { trainingGames } from '@/utils/minigame/games';
import { leftClickModes, multiTouchModes } from '@/utils/minigame/leftClickTraining';
import { reactionModes } from '@/utils/minigame/reactionTraining';
import { minigameCes } from '@/utils/minigame/scoreDisplay';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';

const groups: MinigameRankingGroup[] = [
    { game: 'reaction', rankings: reactionModes.map((mode) => ({ key: mode.rankingKey, game: 'reaction', level: mode.key, density: String(mode.probability) as '25' | '50', order: 'asc', unit: 'ms', min_score: 1, max_score: Number.MAX_SAFE_INTEGER, accept_submissions: true })) },
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
        minigameSettings.value = defaultMinigameSettings();
        local.value.colored = false;
        cy.mockPlayerNameFallback();
        cy.intercept('GET', '/api/minigame/rankings', groups).as('rankings');
        cy.intercept({ method: 'GET', pathname: '/api/minigame/*/rank' }, (request) => {
            const game = groups.find((group) => request.url.includes(`/${group.game}/rank`));
            const records = Object.fromEntries(game?.rankings.map((ranking, index) => [ranking.key, index === 1 ? null : { score: 1234, achieved_at: '2026-10-23T00:00:00Z' }]) ?? []);
            request.reply({ count: 25, players: [{ player_id: 42, rank: Number(request.query.start) + 1, records }] });
        }).as('rank');
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
        local.value.colored = false;
    });

    it('switches both click-training rankings to CES locally without refetching scores', () => {
        const router = mountRanking('/ranking/minigame/left-click');
        cy.wait('@rank');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.text', '1.234');
        cy.get('[data-cy=minigame-ranking-score-display]').should('have.text', 'Time').click();
        cy.get('[data-cy=minigame-replay-link]').first().should('have.text', '25.122');
        cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value: string | null) => {
            expect((JSON.parse(value ?? '{}') as { leftClickScoreDisplay?: string }).leftClickScoreDisplay).to.eq('ces');
        });
        cy.get('.minigame-ranking-table table').extractTableData().should((rows) => {
            expect(rows.at(-1)?.[3]).to.eq('--');
        });
        cy.get('.minigame-ranking-table th[aria-sort=descending]').should('have.length', 1);
        cy.get('@rank.all').should('have.length', 1);
        cy.then(() => router.push('/ranking/minigame/multi-touch'));
        cy.wait('@rank');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.text', '25.122');
        cy.get('[data-cy=minigame-ranking-score-display]').click();
        cy.get('[data-cy=minigame-replay-link]').first().should('have.text', '1.234');
        cy.get('.minigame-ranking-table th[aria-sort=ascending]').should('have.length', 1);
        cy.then(() => router.push('/ranking/minigame/flag-chord'));
        cy.wait('@rank');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.text', '1.234');
        cy.get('[data-cy=minigame-ranking-score-display]').should('not.exist');
    });

    it('colors left-click scores by CES when coloring is enabled', () => {
        mountRanking('/ranking/minigame/left-click');
        cy.wait('@rank');
        const firstScoreCell = () => cy.get('.minigame-ranking-table tbody tr').first().find('td').eq(2);
        firstScoreCell().should(($cell) => expect($cell[0].style.backgroundColor).to.equal(''));
        cy.get('[data-cy=minigame-ranking-color]').should('have.attr', 'aria-pressed', 'false').click().should('have.attr', 'aria-pressed', 'true');
        const ces = minigameCes(1234, 'left-click-b-50-v1') ?? 0;
        firstScoreCell().should('have.css', 'background-color', tinycolor(colorThemes.bvs.value.getColor(ces)).toRgbString());
        cy.get('[data-cy=minigame-ranking-color]').click();
        firstScoreCell().should(($cell) => expect($cell[0].style.backgroundColor).to.equal(''));
    });

    it('groups six reaction columns by level, uses percentages and keeps time display under the CES setting', () => {
        minigameSettings.value.leftClickScoreDisplay = 'ces';
        const router = mountRanking('/ranking/minigame/reaction?sort=reaction-e-50-v1');
        cy.wait('@rank').its('request.query.sort').should('equal', 'reaction-e-50-v1');
        cy.get('.minigame-ranking-table th[scope=colgroup]').should('have.length', 3).each(($heading) => {
            expect($heading.attr('colspan')).to.eq('2');
        });
        cy.get('.minigame-ranking-table thead tr').eq(1).find('button').should('have.length', 6);
        cy.get('[data-cy=minigame-ranking-score-display]').should('not.exist');
        cy.get('.minigame-ranking-table table').extractTableData().should((rows) => {
            expect(rows[1]).to.deep.eq(['25%', '50%', '25%', '50%', '25%', '50%']);
            expect(rows.at(-1)?.slice(2)).to.deep.eq(['1.234', '--', '1.234', '1.234', '1.234', '1.234']);
        });
        cy.contains('.minigame-ranking-table thead button', '25%').click();
        cy.wait('@rank').its('request.query.sort').should('equal', 'reaction-b-25-v1');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.attr', 'href', '/minigame/reaction?player=42&key=b-25-v1').click();
        cy.wrap(router).its('currentRoute.value.name').should('equal', 'minigame-reaction');
    });

    it('opens a deep link with nine columns, sorts, paginates, refreshes and switches groups', () => {
        const router = mountRanking('/ranking/minigame/left-click?sort=left-click-e-87.5-v1&page=2');
        cy.wait('@rank').its('request.query').should('include', { sort: 'left-click-e-87.5-v1', start: '20', end: '40' });
        cy.get('.ranking-selector').should('have.value', 'left-click');
        cy.get('.el-tabs__item.is-active').should('have.text', 'Minigames');
        cy.get('[data-cy=minigame-play-link]').should('have.attr', 'href', '/minigame/left-click');
        cy.get('.minigame-ranking-table tbody tr td').should('have.length', 11);
        cy.get('.minigame-ranking-table tbody').should('contain.text', '1.234').and('contain.text', '--');
        cy.get('[data-cy=minigame-replay-link]').first().should('have.attr', 'href', '/minigame/left-click?player=42&key=b-50-v1');
        cy.get('.minigame-ranking-table tbody tr td').eq(3).find('a').should('not.exist');
        cy.get('.minigame-ranking-table [aria-pressed=true]').should('have.attr', 'aria-label', 'Expert 7/8');
        cy.get('[data-cy=minigame-ranking-color]').should('not.be.disabled');
        cy.get('.minigame-ranking-table [aria-label="Beginner 3/4"]').click();
        cy.wait('@rank').its('request.query').should('include', { sort: 'left-click-b-75-v1', start: '0', end: '20' });
        cy.wrap(router).its('currentRoute.value.query.page').should('equal', '1');
        cy.get('.pagination .btn-next').click();
        cy.wait('@rank').its('request.query.start').should('equal', '20');
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@rank');
        for (const [game, label, columns] of [['multi-touch', 'Multi-touch training', 11], ['flag-chord', 'Flag-and-chord training', 4], ['missing-cell', 'Missing cell training', 5]] as const) {
            cy.get('.ranking-selector').select(game);
            cy.wait('@rank').its('request.query.start').should('equal', '0');
            cy.get('.ranking-selector').should('have.value', game);
            cy.get('.ranking-selector option:checked').should('have.text', label);
            cy.get('.minigame-ranking-table tbody tr td').should('have.length', columns);
            cy.get('[data-cy=minigame-play-link]').should('have.attr', 'href', `/minigame/${game}`);
            cy.get('[data-cy=minigame-replay-link]').first().should('have.attr', 'href', `/minigame/${game}?player=42&key=${game === 'multi-touch' ? 'b-50-v1' : 'b-v1'}`);
        }
        cy.then(() => {
            router.back();
        });
        cy.wait('@rank');
        cy.get('.ranking-selector').should('have.value', 'flag-chord');
        cy.get('[data-cy=minigame-play-link]').should('have.attr', 'href', '/minigame/flag-chord');
        cy.then(() => {
            router.forward();
        });
        cy.wait('@rank');
        cy.get('.ranking-selector').should('have.value', 'missing-cell');
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
