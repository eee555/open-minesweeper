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
        emits: ['completed', 'reset', 'rankingChange'],
        expose: [],
        setup(_props, { emit, slots }) {
            const route = useRoute();
            const key = String(route.name).replace('minigame-', '');
            emit('rankingChange', `${key}-${key === 'left-click' || key === 'multi-touch' ? 'b-50' : 'b'}-v1`);
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
        cy.mount(defineComponent({ expose: [], render: () => h(RouterView) }), { global: { plugins: [i18n, pinia, router], stubs: { transition: false }, config: { globalProperties: { $axios } } } });
    });
}

describe('online minigame score submission', () => {
    beforeEach(() => {
        store.logout();
    });
    afterEach(() => {
        cy.get('@vue').invoke('unmount');
        cy.then(() => {
            store.logout();
        });
    });

    it('uploads a multi-touch replay only on request after login, without requiring a real name', () => {
        cy.intercept('POST', '/api/minigame/multi-touch-b-50-v1/score', { improved: true, record: {} }).as('submit');
        mountGame();
        cy.get('[data-cy=game-multi-touch]').click();
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
            expect(JSON.parse(form.get('replay') ?? 'null')).to.deep.eq(touchReplay);
        });
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.text', 'Uploaded');
    });

    it('uploads only on request, requires login without a real name and clears pending results on restart or game change', () => {
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { improved: true, record: {} }).as('submit');
        mountGame();
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
        }
    });

    it('allows retrying an upload after a failed request', () => {
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { statusCode: 500, body: {} }).as('failedSubmit');
        store.login({ id: 42, username: 'player', realname: '匿名' });
        mountGame();
        cy.get('[data-cy=complete]').click();
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@failedSubmit').its('response.statusCode').should('equal', 500);
        cy.get('[data-cy=minigame-upload]').should('be.enabled').and('have.text', 'Upload score and replay');
        cy.closeElNotifications();
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { improved: true, record: {} }).as('submit');
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit').its('response.statusCode').should('equal', 200);
        cy.get('[data-cy=minigame-upload]').should('be.disabled').and('have.text', 'Uploaded');
        cy.get('@failedSubmit.all').should('have.length', 1);
        cy.get('@submit.all').should('have.length', 1);
    });

    it('refreshes the visible ranking after a successful manual upload', () => {
        cy.viewport(1440, 1000);
        store.login({ id: 42, username: 'player', realname: '匿名' });
        cy.intercept('GET', '/api/minigame/flag-chord-b-v1/summary', { count: 0, players: [], player: { player_id: 42, records: { 'flag-chord-b-v1': null } } }).as('summary');
        cy.intercept('POST', '/api/minigame/flag-chord-b-v1/score', { improved: true, record: {} }).as('submit');
        mountGame();
        cy.get('[data-cy=minigame-ranking-toggle]').click();
        cy.wait('@summary');
        cy.get('[data-cy=complete]').click();
        cy.get('@summary.all').should('have.length', 1);
        cy.get('[data-cy=minigame-upload]').click();
        cy.wait('@submit');
        cy.wait('@summary');
        cy.get('@summary.all').should('have.length', 2);
    });
});
