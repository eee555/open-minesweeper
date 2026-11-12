import { reactive } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import UserPBView from './UserPBView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { UserProfile } from '@/utils/userprofile';

const records = [
    { level: 'e', bv: 100, nf: false, timems: 40000, video_id: 101, rank: 2 },
    { level: 'e', bv: 102, nf: false, timems: 50000, video_id: 102, rank: null },
    { level: 'e', bv: 100, nf: true, timems: 45000, video_id: 103, rank: 3 },
];

function summary(pbRecords: typeof records) {
    return {
        pb: pbRecords,
        records: { collection: {}, skill: {}, typical_time: {} },
        ranks: { collection: {}, skill: {}, typical_time: {} },
    };
}

function interceptSummary(alias: string, body: unknown) {
    cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/summary' }, { body }).as(alias);
}

function mountPB() {
    store.logout();
    const user = reactive(new UserProfile({ id: 42 }));
    const router = createRouter({ history: createMemoryHistory(),
        routes: [
            { path: '/player/:id/pb', name: 'user-pb', component: UserPBView },
            { path: '/player/:id/videos', name: 'user-videos', component: UserPBView },
        ] });
    void router.push('/player/42/pb');
    cy.wrap(router.isReady()).then(() => {
        cy.mount(UserPBView, { props: { user }, global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
    });
    return { router, user };
}

describe('Profile PB tab', () => {
    let initialDark = false;
    beforeEach(() => {
        cy.document().then((document) => {
            initialDark = document.documentElement.classList.contains('dark');
        });
        cy.intercept('GET', '**/api/userprofile/videolist*', []).as('videos');
        interceptSummary('pb', summary(records));
    });
    afterEach(() => {
        cy.document().then((document) => {
            document.documentElement.classList.toggle('dark', initialDark);
        });
    });

    it('uses opaque medals and translucent rank bands with readable text in light and dark modes', () => {
        const bands = [
            { rank: 1, color: 'rgb(255, 192, 0)' },
            { rank: 2, color: 'rgb(160, 160, 160)' },
            { rank: 3, color: 'rgb(205, 127, 50)' },
            { rank: 4, color: 'rgba(64, 158, 255, 0.22)' },
            { rank: 10, color: 'rgba(64, 158, 255, 0.22)' },
            { rank: 11, color: 'rgba(64, 158, 255, 0.14)' },
            { rank: 50, color: 'rgba(64, 158, 255, 0.14)' },
            { rank: 51, color: 'rgba(64, 158, 255, 0.07)' },
            { rank: 100, color: 'rgba(64, 158, 255, 0.07)' },
            { rank: 101, color: 'rgba(0, 0, 0, 0)' },
            { rank: null, color: 'rgba(0, 0, 0, 0)' },
        ];
        interceptSummary('rankRecords', summary(bands.map(({ rank }, index) => ({ ...records[0], bv: 100 + index, rank }))));
        mountPB();
        cy.wait('@rankRecords');
        const timeStyle = { backgroundColor: '', color: '' };
        cy.get('[data-cy=pb-e-100]').should('contain.text', '40.000').then(($cell) => {
            timeStyle.backgroundColor = $cell[0].style.backgroundColor;
            timeStyle.color = $cell[0].style.color;
        });
        cy.get('[data-cy=pb-stat] [data-stat=rank]').click();
        for (const dark of [false, true]) {
            cy.document().then((document) => {
                document.documentElement.classList.toggle('dark', dark);
            });
            bands.forEach(({ rank, color }, index) => {
                cy.get(`[data-cy=pb-e-${100 + index}]`).should('have.css', 'background-color', color).and(($cell) => {
                    expect($cell.text().trim()).to.equal(String(rank ?? '--'));
                    const expectedText = rank !== null && rank <= 3 ? 'rgb(20, 20, 20)' : $cell.closest('.pb-grid').css('color');
                    expect($cell.css('color')).to.equal(expectedText);
                    expect($cell.find('a').css('color')).to.equal($cell.css('color'));
                    expect($cell.css('opacity')).to.equal('1');
                    expect($cell.find('a').css('opacity')).to.equal('1');
                });
            });
            cy.get('[data-cy=pb-grid-e] .pb-cell:empty').should('have.css', 'background-color', 'rgba(0, 0, 0, 0)');
        }
        cy.get('[data-cy=pb-stat] [data-stat=time]').click();
        cy.get('[data-cy=pb-e-100]').should('contain.text', '40.000').and(($cell) => {
            expect($cell[0].style.backgroundColor).to.equal(timeStyle.backgroundColor);
            expect($cell[0].style.color).to.equal(timeStyle.color);
        });
        cy.get('@rankRecords.all').should('have.length', 1);
        cy.get('@videos.all').should('have.length', 0);
    });

    it('switches metrics and NF locally, preserves absent ranks, and links to the same PB video', () => {
        mountPB();
        cy.wait('@pb');
        cy.get('[data-cy=pb-grid-b]').should('contain.text', 'No PB records');
        cy.get('[data-cy=pb-e-100]').should('contain.text', '40.000').find('a').should('have.attr', 'href', '#/video/101');
        cy.get('[data-cy=pb-e-100]').should('have.attr', 'title').and('include', 'BV 100\nTime: 40.000\n');
        cy.get('[data-cy=pb-stat] button').should('have.length', 4);
        cy.get('[data-cy=pb-stat] button[aria-pressed=true]').should('have.length', 1).and('have.attr', 'data-stat', 'time');
        cy.get('[data-cy=pb-stat] [data-stat=bvs]').click();
        cy.get('[data-cy=pb-stat] button[aria-pressed=true]').should('have.length', 1).and('have.attr', 'data-stat', 'bvs');
        cy.get('[data-cy=pb-e-100]').should('contain.text', '2.500');
        cy.get('[data-cy=pb-stat] [data-stat=rank]').focus();
        cy.realPress('Space');
        cy.get('[data-cy=pb-stat] button[aria-pressed=true]').should('have.length', 1).and('have.attr', 'data-stat', 'rank');
        cy.get('[data-cy=pb-e-100]').should('contain.text', '2');
        cy.get('[data-cy=pb-e-102]').should('contain.text', '--').find('a').should('have.attr', 'href', '#/video/102');
        cy.get('[data-cy=pb-summary] input[type=checkbox]').check();
        cy.get('[data-cy=pb-e-100]').should('contain.text', '3').find('a').should('have.attr', 'href', '#/video/103');
        cy.get('@pb.all').should('have.length', 1);
        cy.get('@videos.all').should('have.length', 0);
    });

    it('shows a retryable error rather than an empty-record result', () => {
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/summary' }, { statusCode: 500 }).as('failedPB');
        mountPB();
        cy.wait('@failedPB');
        cy.get('[role=alert]').should('contain.text', 'Could not load PB records');
        cy.get('[data-cy=pb-empty]').should('not.exist');
        interceptSummary('retryPB', summary(records));
        cy.get('[data-cy=refresh-pb]').click();
        cy.wait('@retryPB');
        cy.get('[data-cy=pb-e-100]').should('contain.text', '40.000');
    });

    it('does not fetch a new player in the background and reuses data on returning', () => {
        const { router, user } = mountPB();
        cy.wait('@pb');
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/summary', query: { player_id: '43' } }, { body: summary([]) }).as('otherPB');
        cy.then(() => router.push('/player/42/videos'));
        cy.then(() => {
            user.id = 43;
        });
        cy.get('[data-cy=pb-grid-e]').should('not.exist');
        cy.get('@otherPB.all').should('have.length', 0);
        cy.then(() => {
            user.id = 42;
        });
        cy.then(() => router.push('/player/42/pb'));
        cy.get('[data-cy=pb-e-100]').should('contain.text', '40.000');
        cy.get('@pb.all').should('have.length', 1);
        cy.get('@videos.all').should('have.length', 0);
    });
});
