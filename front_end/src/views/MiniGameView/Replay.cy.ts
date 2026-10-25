import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import App from './App.vue';
import FlagChordTraining from './FlagChordTraining/App.vue';
import LeftClickTraining from './LeftClickTraining/App.vue';
import MissingCellTraining from './MissingCellTraining/App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { loadReplayArchiveCodec } from '@/utils/minigame/archive';
import { encodeMines } from '@/utils/minigame/boardEncoding';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';
import { leftClickModes, LeftClickTraining as LeftClickGame } from '@/utils/minigame/leftClickTraining';
import { isolateMinigameHistory, savedMinigameResults } from '@cy/support/minigame';

const mouse = { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [[0, 16, 16, 2], [10, 32, 0, 1], [10, 0, 0, 2]], specialEvents: [] };

function replyReplay(game: TrainingGame, key: string, source: unknown) {
    cy.then(loadReplayArchiveCodec).then((codec) => {
        cy.intercept({ method: 'GET', pathname: `/api/minigame/${game}/replay`, query: { player: '42', key } }, {
            headers: { 'Content-Type': 'application/x-7z-compressed', 'X-Minigame-Score': '1234' },
            // cy.intercept preserves ArrayBuffer; Buffer bodies are serialized as JSON.
            body: codec.pack(source),
        }).as('replay');
    });
}

function mountReplay(path: string) {
    const router = createRouter({ history: createMemoryHistory(),
        routes: [
            { path: '/minigame',
                component: App,
                children: [
                    { path: 'left-click', name: 'minigame-left-click', component: LeftClickTraining },
                    { path: 'multi-touch', name: 'minigame-multi-touch', component: LeftClickTraining, props: { gameType: 'multi-touch' } },
                    { path: 'flag-chord', name: 'minigame-flag-chord', component: FlagChordTraining },
                    { path: 'missing-cell', name: 'minigame-missing-cell', component: MissingCellTraining },
                ] },
            ...trainingGames.map((key) => ({ path: `/ranking/minigame/${key}`, name: `ranking_minigame_${key}`, component: { expose: [], render: () => null } })),
        ] });
    void router.push(path);
    cy.wrap(router.isReady()).then(() => {
        cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
    });
    return router;
}

describe('online minigame replays', () => {
    isolateMinigameHistory();

    for (const [game, key, source, remaining] of [
        ['left-click', 'b-50-v1', mouse, '030'],
        ['multi-touch', 'b-50-v1', { version: 1, cellSize: 32, initialBoard: mouse.initialBoard, events: [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]] }, '030'],
        ['flag-chord', 'b-v1', { ...mouse, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], events: [[0, 16, 16, 3], [20, 32, 32, 1], [20, 0, 0, 2]] }, '003'],
    ] as const) {
        it(`opens a ${game} 7z replay from its URL without saving or uploading a result`, () => {
            replyReplay(game, key, source);
            const router = mountReplay(`/minigame/${game}?player=42&key=${key}`);
            cy.wait('@replay');
            cy.get('.training-page[data-replay=true]').should('be.visible').and('have.attr', 'data-phase', 'won');
            const prefix = game === 'flag-chord' ? 'flag-chord' : 'training';
            cy.get(`[data-cy=${prefix}-remaining]`).should('have.attr', 'aria-label', remaining);
            cy.get(`[data-cy=${prefix}-time]`).should('have.attr', 'aria-label', '001.234');
            cy.get('.training-controls input[value=b]').should('be.checked');
            cy.get('[data-cy=minigame-replay-position]').should('have.attr', 'max', '1234').and('have.value', '1234');
            cy.get('[data-cy=minigame-replay-position]').invoke('val', '0').trigger('input');
            cy.get('[data-cy=minigame-replay-position]').trigger('change');
            cy.get(`[data-cy=${prefix}-time]`).should('have.attr', 'aria-label', '000.000');
            cy.get('[data-cy=minigame-replay-play]').should('have.attr', 'aria-pressed', 'false');
            cy.get(game === 'multi-touch' ? '.minigame-touch-trace' : '.minigame-replay-trace').should('exist');
            cy.get('[data-cy=minigame-upload]').should('not.exist');
            savedMinigameResults().should('have.length', 0);
            cy.get('.training-frame-counters').click();
            cy.wrap(router).its('currentRoute.value.query').should('deep.equal', {});
            cy.get('.training-page').should('have.attr', 'data-replay', 'false').and('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy=minigame-replay-controls]').should('not.exist');
        });
    }

    it('selects the recorded mode and keeps newly chosen parameters when leaving the replay', () => {
        const mode = leftClickModes.find((item) => item.key === 'e' && item.density === 75);
        if (mode === undefined) throw new Error('Missing expert mode');
        replyReplay('left-click', 'e-75-v1', { ...mouse, initialBoard: encodeMines(mode, new LeftClickGame(mode).board), events: [] });
        const router = mountReplay('/minigame/left-click?player=42&key=e-75-v1');
        cy.wait('@replay');
        cy.get('.training-page[data-replay=true]').should('have.attr', 'data-phase', 'won');
        cy.get('[data-cy=training-level] input[value=e]').should('be.checked');
        cy.get('[data-cy=training-density]').should('have.value', '75');
        cy.get('[data-cy=training-density]').select('87.5');
        cy.wrap(router).its('currentRoute.value.query').should('deep.equal', {});
        cy.get('.training-page').should('have.attr', 'data-replay', 'false').and('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy=training-level] input[value=e]').should('be.checked');
        cy.get('[data-cy=training-density]').should('have.value', '87.5');
        cy.get('[data-cy=training-remaining]').should('have.attr', 'aria-label', '060');
        savedMinigameResults().should('have.length', 0);
    });

    it('reviews all missing-cell boards and times, restoring the completed board after hover', () => {
        const key = 'b-v1';
        replyReplay('missing-cell', key, { version: 1, rounds: Array.from({ length: 10 }, (_, index) => ({ board: 'gAAAAAAAAAA', target: [7, 7], timeMs: index + 100 })) });
        const router = mountReplay(`/minigame/missing-cell?player=42&key=${key}`);
        cy.wait('@replay');
        cy.get('[data-cy=missing-cell-remaining]').should('have.attr', 'aria-label', '000');
        cy.get('[data-cy=missing-cell-round-times] .plot-bar rect').should('have.length', 10);
        cy.get('[data-cy=missing-cell-time-stack] [data-cy="Board 1"]').trigger('mouseenter');
        cy.get('[data-cy=missing-cell-remaining]').should('have.attr', 'aria-label', '010');
        cy.get('[data-cy=missing-cell-time]').should('have.attr', 'aria-label', '000.100');
        cy.get('[data-cy=minigame-board-highlight]').should('exist');
        cy.get('[data-cy=missing-cell-time-stack] [data-cy="Board 1"]').trigger('mouseleave');
        cy.get('[data-cy=missing-cell-remaining]').should('have.attr', 'aria-label', '000');
        cy.get('[data-cy=missing-cell-time]').should('have.attr', 'aria-label', '001.234');
        cy.get('[data-cy=minigame-board-highlight]').should('not.exist');
        savedMinigameResults().should('have.length', 0);
        cy.get('.training-frame-counters').click();
        cy.wrap(router).its('currentRoute.value.query').should('deep.equal', {});
        cy.get('.training-page').should('have.attr', 'data-replay', 'false').and('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy=missing-cell-results]').should('not.exist');
    });

    it('handles invalid links, missing replays and corrupt archives when navigating within one game', () => {
        const key = 'b-50-v1';
        cy.intercept({ method: 'GET', pathname: '/api/minigame/left-click/replay', query: { player: '42', key } }, { statusCode: 404 }).as('missing');
        cy.intercept({ method: 'GET', pathname: '/api/minigame/left-click/replay', query: { player: '43', key } }, { headers: { 'X-Minigame-Score': '1000' }, body: new Uint8Array([1, 2, 3]).buffer }).as('corrupt');
        const router = mountReplay('/minigame/left-click?player=42');
        cy.get('[data-cy=minigame-replay-error]').should('contain.text', 'Invalid replay link parameters.');
        cy.then(() => router.push({ query: { player: '42', key } }));
        cy.wait('@missing');
        cy.get('[data-cy=minigame-replay-error]').should('contain.text', 'No replay found');
        cy.then(() => router.push({ query: { player: '43', key } }));
        cy.wait('@corrupt');
        cy.get('[data-cy=minigame-replay-error]').should('contain.text', 'damaged');
        cy.get('.training-page, [data-cy=minigame-upload]').should('not.exist');
    });
});
