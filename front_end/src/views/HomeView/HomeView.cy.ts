import $axios from '@/http';
import i18n from '@/i18n';
import { serviceConfig } from '@/services/store';
import { local } from '@/store';
import { TournamentState, TournamentSubclass } from '@/utils/ms_const';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';
import { mockVideoInfo } from '@cy/support/videoInfo';

const fixedNow = new Date('2026-07-22T12:00:00Z').getTime();
const fullDay = 86400000;

const newestQueueResponse = {
    101: JSON.stringify({
        state: 'c',
        software: 'e',
        time: '2026-07-22T08:00:00Z',
        player_id: 7,
        level: 'e',
        mode: '00',
        timems: 59987,
        bv: 151,
        cl: 250,
        ce: 170,
    }),
    102: JSON.stringify({
        state: 'd',
        software: 'a',
        time: '2026-07-22T09:00:00Z',
        player_id: 8,
        level: 'i',
        mode: '00',
        right_ce: 0,
        timems: 40234,
        bv: 82,
        cl: 140,
        ce: 96,
    }),
};

const reviewQueueResponse = [
    {
        id: 301,
        player: 9,
        software: 'e',
        level: 'b',
        mode: '00',
        state: 'a',
        cl: 42,
        ce: 25,
        timems: 9876,
        bv: 31,
        upload_time: '2026-07-22T08:00:00Z',
        end_time: '2026-07-22T08:00:10Z',
    },
    {
        id: 302,
        player: 10,
        software: 'a',
        level: 'e',
        mode: '00',
        right_ce: 0,
        state: 'a',
        cl: 260,
        ce: 190,
        timems: 65432,
        bv: 151,
        upload_time: '2026-07-22T09:00:00Z',
        end_time: null,
    },
];

const newsEvents = [
    {
        id: 'news-pb-1',
        category: 'pb',
        occurred_at: fixedNow - 3600000,
        player_id: 7,
        payload: {
            field: 'std:b:10',
            old: { timems: 12340, video_id: 101, rank: 8 },
            new: { timems: 9876, video_id: 102, rank: 3 },
        },
    },
    {
        id: 'news-lsf-1',
        category: 'lsf',
        occurred_at: fixedNow - 7200000,
        player_id: 8,
        payload: {
            video_id: 301,
            video_ids: [301, 302],
            old: { lsf: 3200.5, rank: 40 },
            new: { lsf: 4100.25, rank: 28 },
        },
    },
    {
        id: 'news-eff-1',
        category: 'eff',
        occurred_at: fixedNow - 10800000,
        player_id: 7,
        payload: {
            field: 'thrp:i',
            old: { value: 0.8, video_id: 101, rank: 8, count: null, timems: null },
            new: { value: 0.9, video_id: 102, rank: 3, count: null, timems: null },
        },
    },
];

function normalTournamentResponse() {
    return [
        {
            id: 401,
            name: { en: 'Upcoming Cup' },
            subclass: TournamentSubclass.GSC,
            data: { order: 401, token: 'G00401' },
            start_time: new Date(fixedNow + 2 * fullDay + 3 * 3600000 + 4 * 60000 + 5000).toISOString(),
            end_time: new Date(fixedNow + 3 * fullDay).toISOString(),
            state: TournamentState.Normal,
            host_id: 1,
        },
        {
            id: 402,
            name: { en: 'Ongoing Cup' },
            subclass: TournamentSubclass.Weekly,
            data: { year: 2099, week: 42, tournament_format: 'c' },
            start_time: new Date(fixedNow - fullDay).toISOString(),
            end_time: new Date(fixedNow + 3 * 3600000 + 4 * 60000 + 5000).toISOString(),
            state: TournamentState.Normal,
            host_id: 1,
        },
        {
            id: 403,
            name: { en: 'Finished Cup' },
            subclass: TournamentSubclass.GSC,
            data: { order: 403, token: 'G00403' },
            start_time: new Date(fixedNow - 3 * fullDay).toISOString(),
            end_time: new Date(fixedNow - 2 * 3600000 - 3 * 60000 - 4000).toISOString(),
            state: TournamentState.Normal,
            host_id: 1,
        },
    ];
}

function mountGlobal() {
    return {
        plugins: [i18n, hashRouter()],
        config: {
            globalProperties: {
                $axios,
            },
        },
    };
}

function mockHomeQueueRequests() {
    const newest = Object.entries(newestQueueResponse).map(([id, json]) => ({ id: Number(id), ...JSON.parse(json) as Record<string, unknown> }));
    const metadata = mockVideoInfo([...newest, ...reviewQueueResponse]);
    cy.intercept({ method: 'GET', pathname: '/api/video/newest_queue' }, { body: metadata.slice(0, newest.length) }).as('newestQueue');
    cy.intercept({ method: 'GET', pathname: '/api/video/review_queue' }, { body: metadata.slice(newest.length) }).as('reviewQueue');
    cy.intercept({ method: 'GET', pathname: '/api/tournament/get_list' }, { body: normalTournamentResponse() }).as('normalTournaments');
    cy.intercept({ method: 'GET', pathname: '/api/news/events' }, { body: newsEvents }).as('newsEvents');
}

function configureUserInfoService() {
    serviceConfig.value.userInfoBatchDelay = 0;
    serviceConfig.value.userInfoBatchSize = 100;
    serviceConfig.value.userInfoLastUpdate = 0;
}

function mountHomeView() {
    cy.then(() => import('./App.vue')).then(({ default: App }) => {
        cy.mount(App, { global: mountGlobal() });
    });
    cy.tick(0);
}

describe('HomeView components', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        local.value.language = 'en';
        cy.clock(fixedNow, ['Date']);
        configureUserInfoService();
        mockHomeQueueRequests();
        cy.mockPlayerNameFallback();
    });

    it('renders the real home queue components in the expected tab layout', () => {
        mountHomeView();

        cy.get('.home-news-tabs .el-tabs__item').should('have.length', 4);
        cy.get('.home-news-tabs .el-tabs__item button').should('not.exist');
        cy.get('.home-news-refresh').should('have.length', 1).and('be.visible');
        cy.get('.home-news-refresh').then(($button) => {
            cy.get('.home-news-tabs .el-tabs__item').last().should(($tab) => {
                const [button] = $button.toArray();
                const [tab] = $tab.toArray();
                const buttonRect = button.getBoundingClientRect();
                const tabRect = tab.getBoundingClientRect();
                expect(Math.abs(buttonRect.top - tabRect.top), '与 tab 同一行').to.be.lessThan(12);
                expect(buttonRect.left, '位于 tab 项右侧').to.be.greaterThan(tabRect.right);
            });
        });
        cy.contains('.home-news-tabs .el-tabs__item', 'News').should('be.visible');
        cy.contains('.home-news-tabs .el-tabs__item', 'PB').should('be.visible');
        cy.contains('.home-news-tabs .el-tabs__item', 'LSF').should('be.visible');
        cy.contains('.home-news-tabs .el-tabs__item', 'Eff').should('be.visible');
        cy.wait('@newsEvents');
        cy.get('[data-cy=news-pb]').should('contain.text', 'broke the Beginner 10 PB: 12.340(8) → 9.876(3)');
        cy.get('[data-cy=news-lsf]').should('contain.text', '\'s LSF: 3200.50(40) → 4100.25(28)');
        cy.get('[data-cy=news-eff]').should('contain.text', 'broke the ThrP Intermediate record: 0.800(8) → 0.900(3)');
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').should('have.length', 2);
        cy.contains('.normal-tournament-card', 'Active Tournaments').should('be.visible');
        cy.contains('.el-tabs__item', 'Latest').should('have.class', 'is-active');
        cy.wait('@normalTournaments');
        cy.wait('@newestQueue');
        cy.contains('.el-tabs__item', 'Pending').should('be.visible').click();
        cy.wait('@reviewQueue');
        cy.contains('table:visible', '9.876').should('be.visible');
    });

    it('loads newest videos from the videomanager newest_queue endpoint', () => {
        mountHomeView();

        cy.wait('@newestQueue').its('request.query').should('deep.equal', {});
        cy.contains('.el-tabs__item', 'Latest').should('be.visible');
        cy.contains('table:visible', '59.987').should('be.visible');
        cy.contains('table:visible', '151').should('be.visible');
        cy.contains('table:visible', '2.517').should('be.visible');
        cy.contains('table:visible', '40.234').should('be.visible');
        cy.contains('table:visible', '2.038').should('be.visible');
    });

    it('loads normal tournaments with relative state times', () => {
        mountHomeView();

        cy.wait('@normalTournaments').its('request.query').should('deep.equal', { category: 'normal' });
        cy.get('.normal-tournament-card .el-card__header .el-link').first().should('have.attr', 'href', '/#/tournament');
        cy.contains('.normal-tournament-name .el-link', 'Upcoming Cup').
            should('be.visible').
            and('have.attr', 'href', '/#/tournament/401');
        cy.contains('.normal-tournament-name .el-link', 'Ongoing Cup').
            should('be.visible').
            and('have.attr', 'href', '/#/tournament/402');
        cy.contains('.normal-tournament-name .el-link', 'Finished Cup').
            should('be.visible').
            and('have.attr', 'href', '/#/tournament/403');
        cy.contains('.normal-tournament-card .text-warning', 'starts in 2d 03:04:05').should('be.visible');
        cy.contains('.normal-tournament-card .text-danger', 'ends in 03:04:05').should('be.visible');
        cy.contains('.normal-tournament-card .text-success', 'ended 02:03:04 ago').should('be.visible');
        cy.get('.normal-tournament-card .el-card__header .el-link').eq(1).click();
        cy.wait('@normalTournaments').its('request.query').should('deep.equal', { category: 'normal' });
    });

    it('loads pending review videos from the video API review_queue endpoint', () => {
        mountHomeView();

        cy.contains('.el-tabs__item', 'Pending').should('be.visible');
        cy.contains('.el-tabs__item', 'Pending').click();
        cy.wait('@reviewQueue');
        cy.contains('table:visible', '9.876').should('be.visible');
        cy.contains('table:visible', '31').should('be.visible');
        cy.contains('table:visible', '3.139').should('be.visible');
        cy.contains('table:visible', '65.432').should('be.visible');
        cy.contains('table:visible', '2.308').should('be.visible');
    });

    it('loads news lazily, only for tabs that have been opened', () => {
        mountHomeView();

        cy.wait('@newsEvents');
        cy.get('@newsEvents.all').should('have.length', 1);

        cy.contains('.home-news-tabs .el-tabs__item', 'PB').click();
        cy.wait('@newsEvents');
        cy.get('@newsEvents.all').should('have.length', 2);

        cy.contains('.home-news-tabs .el-tabs__item', 'LSF').click();
        cy.wait('@newsEvents');
        cy.get('@newsEvents.all').should('have.length', 3);

        cy.contains('.home-news-tabs .el-tabs__item', 'Eff').click();
        cy.wait('@newsEvents');
        cy.get('@newsEvents.all').should('have.length', 4);

        cy.contains('.home-news-tabs .el-tabs__item', 'News').click();
        cy.get('.home-news-tabs .el-tabs__item.is-active').should('contain.text', 'News');
        cy.get('[data-cy=news-pb]').should('exist');
        cy.get('@newsEvents.all').should('have.length', 4);
    });

    it('refreshes only the active news tab from the header button', () => {
        mountHomeView();

        cy.wait('@newsEvents').its('request.query.category').should('eq', 'all');
        cy.get('@newsEvents.all').should('have.length', 1);
        cy.get('.home-news-refresh').should('be.visible');
        cy.get('.home-news-refresh').click();
        cy.wait('@newsEvents').its('request.query.category').should('eq', 'all');
        cy.get('@newsEvents.all').should('have.length', 2);

        cy.contains('.home-news-tabs .el-tabs__item', 'PB').click();
        cy.wait('@newsEvents').its('request.query.category').should('eq', 'pb');
        cy.get('@newsEvents.all').should('have.length', 3);
        cy.get('.home-news-refresh').should('not.be.disabled');
        cy.get('.home-news-refresh').click();
        cy.wait('@newsEvents').its('request.query.category').should('eq', 'pb');
        cy.get('@newsEvents.all').should('have.length', 4);
    });
});
