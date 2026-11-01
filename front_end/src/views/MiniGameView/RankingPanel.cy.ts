import { defineComponent, h, ref } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import App from './App.vue';
import FlagChordTraining from './FlagChordTraining/App.vue';
import LeftClickTraining from './LeftClickTraining/App.vue';
import MissingCellTraining from './MissingCellTraining/App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { flagChordModes } from '@/utils/minigame/flagChordTraining';
import { trainingGames } from '@/utils/minigame/games';
import { getMinigameDatabase, MINIGAME_RESULTS_STORE } from '@/utils/minigame/history';
import { leftClickModes, multiTouchModes } from '@/utils/minigame/leftClickTraining';
import { missingCellModes } from '@/utils/minigame/missingCellTraining';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { isolateMinigameHistory } from '@cy/support/minigame';

function mountGame() {
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
            ...trainingGames.map((game) => ({ path: `/ranking/minigame/${game}`, name: `ranking_minigame_${game}`, component: { expose: [], render: () => null } })),
        ] });
    void router.push('/minigame/left-click');
    cy.wrap(router.isReady()).then(() => {
        cy.mount(defineComponent({ expose: [],
            setup() {
                const clicks = ref(0);
                return () => h('div', { style: { paddingTop: '56px' } }, [
                    h('header', { class: 'site-header', style: { position: 'fixed', top: 0, left: 0, right: 0, height: '56px' }, 'data-cy': 'test-menu' }, [
                        h('button', { 'data-cy': 'test-menu-button',
                            onClick: () => {
                                clicks.value++;
                            } }, `Menu ${clicks.value}`),
                    ]),
                    h('input', { 'data-cy': 'outside-input', 'aria-label': 'Outside drawer' }),
                    h(RouterView),
                ]);
            } }), { global: { plugins: [i18n, pinia, router], stubs: { transition: false }, config: { globalProperties: { $axios } } } });
    });
}

const score = { score: 1234, achieved_at: '2026-10-24T08:00:00Z' };

describe('current minigame ranking', () => {
    isolateMinigameHistory();

    beforeEach(() => {
        cy.viewport(1440, 1000);
        store.logout();
        minigameSettings.value = defaultMinigameSettings();
        cy.mockPlayerNameFallback();
    });
    afterEach(() => {
        cy.get('@vue').invoke('unmount');
        cy.then(() => {
            store.logout();
            minigameSettings.value = defaultMinigameSettings();
        });
    });

    it('follows game modes in a drawer below the menu without blocking the page', () => {
        cy.intercept('GET', '/api/minigame/*/summary', (request) => {
            const key = new URL(request.url).pathname.split('/').at(-2) ?? '';
            request.reply({ count: 1, players: [{ player_id: 7, rank: 1, records: { [key]: score } }], player: null });
        }).as('summary');
        mountGame();
        cy.get('[data-cy=minigame-ranking-panel]').should('not.exist');
        cy.get('@summary.all').should('have.length', 0);
        cy.get('[data-cy=minigame-ranking-toggle]').click();
        cy.wait('@summary').its('request.url').should('include', '/left-click-b-50-v1/summary');
        cy.get('[data-cy=minigame-ranking-panel] thead th').should('have.length', 4);
        cy.get('[data-cy=minigame-ranking-panel] caption').should('have.text', 'Beginner · 1/2');
        cy.get('[data-cy=minigame-ranking-score]').should('have.text', '1.234').and('have.attr', 'href', '/minigame/left-click?player=7&key=b-50-v1');
        cy.get('[data-cy=minigame-ranking-ces]').should('have.text', '25.122').and('have.attr', 'href', '/minigame/left-click?player=7&key=b-50-v1');
        cy.then(() => {
            minigameSettings.value.leftClickScoreDisplay = 'ces';
        });
        cy.get('[data-cy=minigame-ranking-score]').should('have.text', '1.234');
        cy.get('[data-cy=minigame-ranking-ces]').should('have.text', '25.122');
        cy.get('.el-drawer.rtl').should('be.visible').and('have.attr', 'aria-label', 'Rankings');
        cy.get('.el-drawer__footer [data-cy=minigame-ranking-link]').should('have.text', 'Full rankings').and('have.attr', 'href', '/ranking/minigame/left-click');
        cy.get('[data-cy=test-menu]').then(($menu) => {
            cy.get('.el-drawer.rtl').should(($drawer) => {
                expect($drawer[0].getBoundingClientRect().top).to.be.at.least($menu[0].getBoundingClientRect().bottom);
            });
        });
        cy.get('.el-modal-drawer').should('have.class', 'is-penetrable').and('have.css', 'pointer-events', 'none');
        cy.get('[data-cy=test-menu-button]').click();
        cy.get('[data-cy=test-menu-button]').should('have.text', 'Menu 1');
        cy.get('[data-cy=outside-input]').type('still interactive');
        cy.get('[data-cy=outside-input]').should('have.value', 'still interactive');
        cy.get('body').should('not.have.class', 'el-popup-parent--hidden');
        cy.get('[data-cy=training-level] input[value=i]').parent().click();
        cy.wait('@summary').its('request.url').should('include', '/left-click-i-50-v1/summary');
        cy.get('[data-cy=training-density]').select('75');
        cy.wait('@summary').its('request.url').should('include', '/left-click-i-75-v1/summary');
        cy.get('[data-cy=game-multi-touch]').click();
        cy.wait('@summary').its('request.url').should('include', '/multi-touch-b-50-v1/summary');
        cy.get('[data-cy=minigame-ranking-ces]').should('have.text', '25.122');
        cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', '/ranking/minigame/multi-touch');
        cy.get('[data-cy=game-flag-chord]').click();
        cy.wait('@summary').its('request.url').should('include', '/flag-chord-b-v1/summary');
        cy.get('[data-cy=minigame-ranking-ces]').should('not.exist');
        cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', '/ranking/minigame/flag-chord');
        cy.get('[data-cy=flag-chord-level] input[value=i]').parent().click();
        cy.wait('@summary').its('request.url').should('include', '/flag-chord-i-v1/summary');
        cy.get('[data-cy=game-missing-cell]').click();
        cy.wait('@summary').its('request.url').should('include', '/missing-cell-b-v1/summary');
        cy.get('[data-cy=minigame-ranking-link]').should('have.attr', 'href', '/ranking/minigame/missing-cell');
        cy.get('[data-cy=missing-cell-level] input[value=e]').parent().click();
        cy.wait('@summary').its('request.url').should('include', '/missing-cell-e-v1/summary');
        cy.get('.el-drawer__close-btn').click();
        cy.get('[data-cy=minigame-ranking-panel]').should('not.exist');
        cy.get('[data-cy=minigame-ranking-toggle]').should('be.visible').and('have.attr', 'aria-expanded', 'false');
        cy.get('@summary.all').should('have.length', 8);
    });

    it('switches history and rankings in one drawer and restores both bookmarks after closing', () => {
        cy.intercept('GET', '/api/minigame/*/summary', { count: 0, players: [], player: null }).as('summary');
        mountGame();
        cy.get('[data-cy=minigame-ranking-toggle]').then(($ranking) => {
            cy.get('[data-cy=minigame-history-toggle]').should(($history) => {
                expect($history[0].getBoundingClientRect().top).to.be.at.least($ranking[0].getBoundingClientRect().bottom);
            });
        });
        cy.get('[data-cy=minigame-history-toggle]').click();
        cy.get('[data-cy=minigame-history-panel]').should('be.visible');
        cy.get('[data-cy=minigame-ranking-panel], [data-cy=minigame-ranking-link]').should('not.exist');
        cy.get('@summary.all').should('have.length', 0);
        cy.get('[data-cy=minigame-drawer-ranking]').click();
        cy.wait('@summary');
        cy.get('.el-drawer.rtl').should('have.length', 1).and('have.attr', 'aria-label', 'Rankings');
        cy.get('[data-cy=minigame-history-panel]').should('not.exist');
        cy.get('[data-cy=minigame-ranking-panel]').should('be.visible');
        cy.get('[data-cy=minigame-drawer-history]').click();
        cy.get('.el-drawer.rtl').should('have.length', 1).and('have.attr', 'aria-label', 'Local history');
        cy.get('[data-cy=minigame-ranking-panel]').should('not.exist');
        cy.get('.el-drawer__close-btn').click();
        cy.get('[data-cy=minigame-ranking-toggle]').should('be.visible');
        cy.get('[data-cy=minigame-history-toggle]').should('be.visible');
    });

    it('filters local history by the selected game, level and density while the drawer stays open', () => {
        cy.then(async () => {
            const db = await getMinigameDatabase();
            const configs = [
                { game: 'left-click', mode: leftClickModes[0] },
                { game: 'left-click', mode: leftClickModes[1] },
                { game: 'left-click', mode: leftClickModes[3] },
                { game: 'multi-touch', mode: multiTouchModes[0] },
                { game: 'flag-chord', mode: flagChordModes[0] },
                { game: 'missing-cell', mode: missingCellModes[0] },
            ] as const;
            for (const [index, config] of configs.entries()) {
                await db.add(MINIGAME_RESULTS_STORE, { ...config, playedAt: Date.now(), scoreMs: (index + 1) * 1000, replay: new ArrayBuffer(0) });
            }
        });
        const expectTime = (time: string, ces?: string) => {
            cy.get('[data-cy=minigame-history-panel] table').extractTableData().should((rows) => {
                expect(rows).to.have.length(2);
                expect(rows[1].slice(1)).to.deep.equal(ces !== undefined ? [time, ces] : [time]);
            });
        };
        mountGame();
        cy.get('[data-cy=minigame-history-toggle]').click();
        expectTime('1.000', '31.000');
        cy.get('[data-cy=training-density]').select('75');
        expectTime('2.000', '7.500');
        cy.get('[data-cy=training-level] input[value=i]').parent().click();
        cy.get('[data-cy=minigame-history-panel]').should('contain.text', 'No matching local results');
        cy.get('.history-row').should('not.exist');
        cy.get('[data-cy=training-density]').select('50');
        expectTime('3.000', '42.333');
        cy.get('[data-cy=game-multi-touch]').click();
        expectTime('4.000', '7.750');
        cy.get('[data-cy=game-flag-chord]').click();
        expectTime('5.000');
        cy.get('[data-cy=game-missing-cell]').click();
        expectTime('6.000');
    });

    it('shows a logged-in player outside the first page, avoids duplicates and reloads after logout', () => {
        let inFirstPage = false;
        store.login({ id: 42, username: 'player' });
        cy.intercept('GET', '/api/minigame/*/summary', (request) => {
            const key = 'left-click-b-50-v1';
            request.reply({ count: 25,
                players: [{ player_id: inFirstPage ? 42 : 7, rank: 1, records: { [key]: score } }],
                player: store.user.id === 42 ? { player_id: 42, records: { [key]: { ...score, rank: inFirstPage ? 1 : 25 } } } : null });
        }).as('summary');
        mountGame();
        cy.get('[data-cy=minigame-ranking-toggle]').click();
        cy.wait('@summary');
        cy.get('.personal-position[data-player="42"]').should('have.attr', 'aria-current', 'true').find('td').first().should('have.text', '25');
        cy.then(() => {
            inFirstPage = true;
        });
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@summary');
        cy.get('[data-cy=minigame-ranking-panel] tr[data-player="42"]').should('have.length', 1).and('have.attr', 'aria-current', 'true');
        cy.then(() => {
            store.logout();
        });
        cy.wait('@summary');
        cy.get('[data-cy=minigame-ranking-panel] [aria-current=true]').should('not.exist');
        cy.get('[data-cy=minigame-ranking-unranked]').should('not.exist');
    });

    it('offers refresh after a load failure and shows an unranked logged-in player', () => {
        let failed = true;
        store.login({ id: 42, username: 'player' });
        cy.intercept('GET', '/api/minigame/*/summary', (request) => {
            request.reply(failed ? { statusCode: 500 } : { body: { count: 0, players: [], player: { player_id: 42, records: { 'left-click-b-50-v1': null } } } });
        }).as('summary');
        mountGame();
        cy.get('[data-cy=minigame-ranking-toggle]').click();
        cy.wait('@summary');
        cy.get('[data-cy=minigame-ranking-panel] [role=alert]').should('be.visible');
        cy.then(() => {
            failed = false;
        });
        cy.get('[data-cy=minigame-ranking-refresh]').click();
        cy.wait('@summary');
        cy.get('[data-cy=minigame-ranking-panel] [role=alert]').should('not.exist');
        cy.get('[data-cy=minigame-ranking-unranked]').should('be.visible');
    });
});
