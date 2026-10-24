/* eslint-disable vue/one-component-per-file -- Each case mounts a render-only lifecycle fixture. */
import { defineComponent, h, KeepAlive, ref } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import ProfilePins from './ProfilePins.vue';
import UserMedalView from './UserMedalView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { MedalItem, PlayerMedals } from '@/services/medalService';
import { store } from '@/store';

function summary(scanPending: boolean, series = '实名在册'): PlayerMedals {
    const item: MedalItem = {
        code: 'novice.registered',
        series,
        subseries: '',
        kind: 'once',
        stage: 1,
        stage_count: 1,
        direction: 'asc',
        current_value: 1,
        next_threshold: null,
        granted_at: '2026-01-01',
        video_id: null,
        tournament_id: null,
        rank: null,
        hidden: false,
        annotation: '',
        score: 1,
        grant_id: 1,
        scope_key: '',
        thresholds: [1],
    };
    return {
        scan_pending: scanPending,
        score: scanPending ? 0 : 1,
        max_pins: 6,
        pin_ids: scanPending ? [] : [1],
        pins: scanPending ? [] : [item],
        series: scanPending ? [] : [{ series, items: [item] }],
    };
}

function deferred() {
    let resolve!: (value: { data: PlayerMedals }) => void;
    let reject!: (reason: Error) => void;
    const promise = new Promise<{ data: PlayerMedals }>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

function createProfileRouter() {
    const page = defineComponent({ expose: [], render: () => h('div', 'Profile tab') });
    return createRouter({
        history: createMemoryHistory(),
        routes: [
            { path: '/', redirect: '/player/1/top' },
            ...['top', 'pb', 'record', 'upload'].map((tab) => ({ path: `/player/:id/${tab}`, name: `user-${tab}`, component: page })),
        ],
    });
}

function globalOptions(router = createProfileRouter()) {
    return { plugins: [i18n, router], config: { globalProperties: { $axios } } };
}

describe('player medal subscriptions', () => {
    afterEach(() => {
        store.player.id = 0;
    });

    for (const outcome of ['resolve', 'reject'] as const) {
        it(`does not replace the new player's sidebar after an old ${outcome}`, () => {
            const playerId = ref(outcome === 'resolve' ? 8101 : 8103);
            const old = deferred();
            const get = cy.stub($axios, 'get');
            get.onFirstCall().returns(old.promise);
            get.onSecondCall().resolves({ data: summary(false, '录像过审') });
            cy.mount(defineComponent({
                expose: [],
                render: () => h(ProfilePins, { userId: playerId.value }),
            }), { global: globalOptions() });
            cy.then(() => {
                playerId.value += 1;
            });
            cy.get('.pins .series').should('have.text', 'Reviewed');
            cy.then(() => {
                if (outcome === 'resolve') old.resolve({ data: summary(false) });
                else old.reject(new Error('old request failed'));
            });
            cy.get('.pins .series').should('have.text', 'Reviewed');
            cy.then(() => expect(get.callCount).to.equal(2));
        });
    }

    it('shares a request and scan updates between sidebar and page, and reuses data on activation', () => {
        cy.clock();
        store.player.id = 8201;
        const showPage = ref(true);
        const get = cy.stub($axios, 'get');
        get.onFirstCall().resolves({ data: summary(true) });
        get.onSecondCall().resolves({ data: summary(false) });
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [
                h(ProfilePins, { userId: store.player.id }),
                h(KeepAlive, null, () => (showPage.value ? h(UserMedalView) : h('div', 'Other tab'))),
            ]),
        }), { global: globalOptions() });
        cy.get('.scan-pending').should('contain', 'Historical medals');
        cy.then(() => expect(get.callCount).to.equal(1));
        cy.tick(2000);
        cy.get('.medal-tile').should('have.length', 1);
        cy.get('.pins .pin').should('have.length', 1);
        cy.get('.scan-pending').should('not.exist');
        cy.then(() => {
            showPage.value = false;
        });
        cy.contains('Other tab').should('be.visible');
        cy.then(() => {
            showPage.value = true;
        });
        cy.get('.medal-tile').should('have.length', 1);
        cy.then(() => expect(get.callCount).to.equal(2));
    });

    it('stops polling and ignores player changes while a KeepAlive page is inactive', () => {
        cy.clock();
        store.player.id = 8301;
        const showPage = ref(true);
        const get = cy.stub($axios, 'get').resolves({ data: summary(true) });
        cy.mount(defineComponent({
            expose: [],
            render: () => h(KeepAlive, null, () => (showPage.value ? h(UserMedalView) : h('div', 'Other tab'))),
        }), { global: globalOptions() });
        cy.get('.scan-pending').should('be.visible');
        cy.then(() => {
            showPage.value = false;
        });
        cy.contains('Other tab').should('be.visible');
        cy.then(() => {
            store.player.id = 8302;
        });
        cy.tick(30_000);
        cy.then(() => expect(get.callCount).to.equal(1));
        cy.then(() => {
            showPage.value = true;
        });
        cy.get('.scan-pending').should('be.visible');
        cy.then(() => expect(get.callCount).to.equal(2));
    });

    it('refreshes expired sidebar data on tab changes while reusing fresh data and inflight requests', () => {
        cy.clock();
        const router = createProfileRouter();
        const showSidebar = ref(true);
        const pending = deferred();
        const updated = summary(false, '录像过审');
        const get = cy.stub($axios, 'get');
        get.onFirstCall().resolves({ data: summary(false) });
        get.onSecondCall().returns(pending.promise);
        get.onThirdCall().resolves({ data: updated });
        cy.then(() => router.push('/player/8401/top'));
        cy.mount(defineComponent({
            expose: [],
            render: () => h(KeepAlive, null, () => (showSidebar.value ? h(ProfilePins, { userId: 8401 }) : h('div', 'Sidebar inactive'))),
        }), { global: globalOptions(router) });
        cy.get('.pins .series').should('have.text', 'Registered');

        cy.then(() => router.push('/player/8401/pb'));
        cy.then(() => expect(get.callCount).to.equal(1));
        cy.tick(30_001);
        cy.then(() => router.push('/player/8401/record'));
        cy.then(() => expect(get.callCount).to.equal(2));
        cy.get('.pins .series').should('have.text', 'Registered');
        cy.then(() => router.push('/player/8401/upload'));
        cy.then(() => {
            expect(get.callCount).to.equal(2);
            pending.resolve({ data: updated });
        });
        cy.get('.pins .series').should('have.text', 'Reviewed');

        cy.then(() => {
            showSidebar.value = false;
        });
        cy.contains('Sidebar inactive').should('be.visible');
        cy.tick(30_001);
        cy.then(() => router.push('/player/8401/top'));
        cy.then(() => {
            expect(get.callCount).to.equal(2);
            showSidebar.value = true;
        });
        cy.get('.pins .series').should('have.text', 'Reviewed');
        cy.then(() => expect(get.callCount).to.equal(3));
    });
});
