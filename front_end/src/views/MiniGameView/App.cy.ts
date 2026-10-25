import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView, useRoute } from 'vue-router';

import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { trainingGames } from '@/utils/minigame/games';

const replay = { version: 1, cellSize: 32, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], events: [], specialEvents: [] };
const touchReplay = { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]] };

function mountGame() {
    const game = defineComponent({
        emits: ['completed', 'reset'],
        expose: [],
        setup(_props, { emit, slots }) {
            const route = useRoute();
            return () => h('div', [
                h('button', { 'data-cy': 'complete',
                    onClick: () => {
                        const touch = route.name === 'minigame-multi-touch';
                        emit('completed', touch ? 'multi-touch-b-50-v1' : 'flag-chord-b-v1', 1234, touch ? touchReplay : replay);
                    } }, 'Complete'),
                h('button', { 'data-cy': 'reset',
                    onClick: () => {
                        emit('reset');
                    } }, 'Restart'),
                slots.resultActions?.(),
            ]);
        },
    });
    const router = createRouter({ history: createMemoryHistory(),
        routes: [
            { path: '/minigame', component: App, children: trainingGames.map((key) => ({ path: key, name: `minigame-${key}`, component: game })) },
            ...trainingGames.map((key) => ({ path: `/ranking/minigame/${key}`, name: `ranking_minigame_${key}`, component: { expose: [], render: () => null } })),
        ] });
    void router.push('/minigame/flag-chord');
    cy.wrap(router.isReady()).then(() => {
        cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
    });
    return router;
}

describe('online minigame score submission', () => {
    beforeEach(() => {
        store.logout();
    });
    afterEach(() => {
        store.logout();
    });

    it('uploads a multi-touch replay only on request after login, without requiring a real name', () => {
        cy.intercept('POST', '/api/minigame/multi-touch-b-50-v1/score', { improved: true, record: {} }).as('submit');
        mountGame();
        cy.get('[data-cy=game-multi-touch]').click();
        cy.get('[data-cy=complete]').click();
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.attr', 'title', 'Log in to upload your score and replay');
        cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', '/ranking/minigame/multi-touch');
        cy.get('@submit.all').should('have.length', 0);
        cy.then(() => {
            store.login({ id: 42, username: 'player', realname: '匿名' });
        });
        cy.get('[data-cy=minigame-upload]').should('be.enabled');
        cy.get('@submit.all').should('have.length', 0);
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit').its('request.body').should((body: string) => {
            const form = new URLSearchParams(body);
            expect(form.get('score')).to.eq('1234');
            expect(JSON.parse(form.get('replay') ?? 'null')).to.deep.eq(touchReplay);
        });
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.text', 'Uploaded');
    });

    it('uploads only on request, requires login without a real name and clears pending results on restart or game change', () => {
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { improved: true, record: {} }).as('submit');
        const router = mountGame();
        cy.get('[data-cy=minigame-upload]').should('not.exist');
        cy.get('[data-cy=complete]').click();
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.attr', 'title', 'Log in to upload your score and replay');
        cy.get('@submit.all').should('have.length', 0);
        cy.then(() => {
            store.login({ id: 42, username: 'player', realname: '匿名' });
        });
        cy.get('[data-cy=minigame-upload]').should('be.enabled');
        cy.get('@submit.all').should('have.length', 0);
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit').its('request.body').should((body: string) => {
            const form = new URLSearchParams(body);
            expect(form.get('score')).to.eq('1234');
            expect(JSON.parse(form.get('replay') ?? 'null')).to.deep.eq(replay);
        });
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.text', 'Uploaded');
        cy.get('[data-cy=reset]').click();
        cy.get('[data-cy=minigame-upload]').should('not.exist');
        cy.then(() => {
            store.user.is_banned = true;
        });
        cy.get('[data-cy=complete]').click();
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.attr', 'title', 'Banned accounts cannot upload');
        cy.get('@submit.all').should('have.length', 1);
        for (const key of trainingGames) {
            cy.get(`[data-cy=game-${key}]`).click();
            cy.get('[data-cy=minigame-upload]').should('not.exist');
            cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', `/ranking/minigame/${key}`);
        }
        cy.get('[data-cy=minigame-ranking-link]').click();
        cy.wrap(router).its('currentRoute.value.name').should('equal', 'ranking_minigame_missing-cell');
    });

    it('allows retrying an upload after a failed request', () => {
        let attempts = 0;
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', (request) => {
            attempts++;
            request.reply(attempts === 1 ? { statusCode: 500 } : { body: { improved: true, record: {} } });
        }).as('submit');
        store.login({ id: 42, username: 'player', realname: '匿名' });
        mountGame();
        cy.get('[data-cy=complete]').click();
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit').its('response.statusCode').should('equal', 500);
        cy.get('[data-cy=minigame-upload]').should('be.enabled').and('have.text', 'Upload score and replay');
        cy.closeElNotifications();
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit').its('response.statusCode').should('equal', 200);
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.text', 'Uploaded');
        cy.get('@submit.all').should('have.length', 2);
    });
});
