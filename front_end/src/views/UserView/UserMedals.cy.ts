/* eslint-disable vue/one-component-per-file -- Each case mounts a render-only lifecycle fixture. */
import { defineComponent, h, KeepAlive, ref } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import ProfilePins from './ProfilePins.vue';
import UserMedalView from './UserMedalView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { MedalItem, PlayerMedals } from '@/services/medalService';
import { uploadVideoFile } from '@/services/videoUploadService';
import { store } from '@/store';
import { MedalDirection, MedalKind, MedalSeries } from '@/utils/medal_const';

function summary(scanPending: boolean, series: MedalSeries = MedalSeries.REGISTERED): PlayerMedals {
    const item: MedalItem = {
        code: series === MedalSeries.REVIEWED ? 'novice.review' : 'novice.realname',
        series,
        subseries: '',
        kind: MedalKind.ONCE,
        stage: 1,
        stage_count: 1,
        direction: MedalDirection.ASC,
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

function deferred<T = PlayerMedals>() {
    let resolve!: (value: { data: T }) => void;
    let reject!: (reason: Error) => void;
    const promise = new Promise<{ data: T }>((resolvePromise, rejectPromise) => {
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
            ...['top', MedalKind.PB, 'record', 'upload'].map((tab) => ({ path: `/player/:id/${tab}`, name: `user-${tab}`, component: page })),
        ],
    });
}

function globalOptions(router = createProfileRouter()) {
    return { plugins: [i18n, router], config: { globalProperties: { $axios } } };
}

describe('player medal subscriptions', () => {
    afterEach(() => {
        store.player.id = 0;
        store.user.id = 0;
    });

    it('filters locally and previews locked tiers without selecting pins', () => {
        store.player.id = 8980 + Cypress.currentRetry;
        const data = summary(false);
        const locked = { ...data.series[0].items[0], code: 'ability.time.b', series: MedalSeries.BREAKTHROUGH, kind: MedalKind.PB, stage: null, grant_id: null, thresholds: [20000, 15000, 12000, 10000, 8000, 6000, 5000, 4000, 3000, 2000, 1000], next_threshold: 20000, stage_count: 11 };
        data.series.push({ series: MedalSeries.BREAKTHROUGH, items: [locked] });
        const get = cy.stub($axios, 'get').resolves({ data });
        cy.mount(UserMedalView, { global: globalOptions() });
        cy.get('.medal-row').should('have.length', 2);
        cy.get('.filters button').eq(1).click();
        cy.get('.medal-row').should('have.length', 1);
        cy.get('.filters button').eq(0).click();
        cy.get('.stage-track').first().find('button').last().click();
        cy.get('.medal-detail').should('contain.text', 'Sub1').and('contain.text', 'Not earned');
        cy.get('.stage-node').should('have.length', 12);
        cy.then(() => expect(get.callCount).to.equal(1));
    });

    it('keeps pending pins on save failure and cancels back to saved pins', () => {
        store.player.id = 8990 + Cypress.currentRetry;
        store.user.id = store.player.id;
        cy.stub($axios, 'get').resolves({ data: summary(false) });
        const put = cy.stub($axios, 'put').rejects(new Error('offline'));
        cy.mount(UserMedalView, { global: globalOptions() });
        cy.contains('button', 'Manage pins').click();
        cy.contains('.row-summary button', 'Unpin').click();
        cy.get('.pin-preview li').should('have.length', 0);
        cy.get('.filters button').eq(1).click();
        cy.contains('button', 'Save pins').click();
        cy.get('.message').should('contain.text', 'Could not save pins');
        cy.get('.pin-preview li').should('have.length', 0);
        cy.then(() => expect(put).to.have.been.calledWith('/api/medal/pins', JSON.stringify({ grant_ids: [] })));
        cy.contains('button', 'Cancel changes').click();
        cy.get('.pin-preview li').should('have.length', 1);
    });

    it('updates an already open page and pins after upload processing without reloading', () => {
        cy.clock();
        const playerId = 8901 + Cypress.currentRetry;
        store.player.id = playerId;
        const waiting = deferred<{ user_id: number; pending: boolean }>();
        const completed = deferred<{ user_id: number; pending: boolean }>();
        const get = cy.stub($axios, 'get');
        get.onFirstCall().resolves({ data: summary(false) });
        get.onSecondCall().returns(waiting.promise);
        get.onThirdCall().returns(completed.promise);
        get.onCall(3).resolves({ data: summary(false, MedalSeries.REVIEWED) });
        cy.stub($axios, 'post').resolves({ data: { type: 'success', data: { id: 123, state: 'c' } } });
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [h(ProfilePins, { userId: playerId }), h(UserMedalView)]),
        }), { global: globalOptions() });
        cy.get('.pins .series').should('have.text', 'Registered');
        cy.then(() => uploadVideoFile(new File(['video'], 'test.avf')));
        cy.tick(1000);
        cy.wrap(get).should('have.callCount', 2);
        cy.then(() => {
            waiting.resolve({ data: { user_id: playerId, pending: true } });
            // Let the async status handler schedule its next timer before ticking again.
            return waiting.promise;
        });
        cy.get('.pins .series').should('have.text', 'Registered');
        cy.tick(2000);
        cy.wrap(get).should('have.callCount', 3);
        cy.then(() => {
            completed.resolve({ data: { user_id: playerId, pending: false } });
            return completed.promise;
        });
        cy.get('.pins .series').should('have.text', 'Reviewed');
        cy.get('.medal-page .row-summary h3').should('have.text', 'Reviewed');
        cy.tick(300_000);
        cy.then(() => expect(get.callCount).to.equal(4));
    });

    for (const outcome of ['resolve', 'reject'] as const) {
        it(`does not replace the new player's sidebar after an old ${outcome}`, () => {
            const playerId = ref(outcome === 'resolve' ? 8101 : 8103);
            const old = deferred();
            const get = cy.stub($axios, 'get');
            get.onFirstCall().returns(old.promise);
            get.onSecondCall().resolves({ data: summary(false, MedalSeries.REVIEWED) });
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
        cy.get('.medal-row').should('have.length', 1);
        cy.get('.pins .pin').should('have.length', 1);
        cy.get('.scan-pending').should('not.exist');
        cy.then(() => {
            showPage.value = false;
        });
        cy.contains('Other tab').should('be.visible');
        cy.then(() => {
            showPage.value = true;
        });
        cy.get('.medal-row').should('have.length', 1);
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
        const updated = summary(false, MedalSeries.REVIEWED);
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
