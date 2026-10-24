import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { trainingGames } from '@/utils/minigame/games';

describe('online minigame score submission', () => {
    beforeEach(() => {
        store.logout();
    });
    afterEach(() => {
        store.logout();
    });

    it('submits completed games for a logged-in player without a real name and skips anonymous or banned players', () => {
        const replay = { version: 1, cellSize: 32, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], events: [], specialEvents: [] };
        const game = defineComponent({
            emits: ['completed'],
            expose: [],
            setup(_props, { emit }) {
                return () => h('button', { 'data-cy': 'complete',
                    onClick: () => {
                        emit('completed', 'flag-chord-b-v1', 1234, replay);
                    } }, 'Complete');
            },
        });
        const router = createRouter({ history: createMemoryHistory(),
            routes: [
                { path: '/minigame', component: App, children: trainingGames.map((key) => ({ path: key, name: `minigame-${key}`, component: game })) },
                ...trainingGames.map((key) => ({ path: `/ranking/minigame/${key}`, name: `ranking_minigame_${key}`, component: { expose: [], render: () => null } })),
            ] });
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { improved: true, record: {} }).as('submit');
        void router.push('/minigame/flag-chord');
        cy.wrap(router.isReady()).then(() => {
            cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        });
        cy.get('[data-cy=complete]').click();
        cy.get('@submit.all').should('have.length', 0);
        cy.then(() => {
            store.login({ id: 42, username: 'player', realname: '匿名' });
        });
        cy.get('[data-cy=complete]').click();
        cy.wait('@submit').its('request.body').should((body: string) => {
            const form = new URLSearchParams(body);
            expect(form.get('score')).to.eq('1234');
            expect(JSON.parse(form.get('replay') ?? 'null')).to.deep.eq(replay);
        });
        cy.then(() => {
            store.user.is_banned = true;
        });
        cy.get('[data-cy=complete]').click();
        cy.get('@submit.all').should('have.length', 1);
        for (const key of trainingGames) {
            cy.get(`[data-cy=game-${key}]`).click();
            cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', `/ranking/minigame/${key}`);
        }
        cy.get('[data-cy=minigame-ranking-link]').click();
        cy.wrap(router).its('currentRoute.value.name').should('equal', 'ranking_minigame_missing-cell');
    });
});
