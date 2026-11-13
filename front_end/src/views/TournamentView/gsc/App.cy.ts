
import type AutoUploader from '../common/AutoUploader.vue';
import type { AutoUploadVideo } from '../common/utils';

import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { LoginStatus } from '@/utils/common/structInterface';
import { MS_Mode, TournamentState, TournamentSubclass } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';
import { VideoAbstract } from '@/utils/videoabstract';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const tournamentId = 7;

function gscTournament() {
    return new Tournament({
        id: tournamentId,
        subclass: TournamentSubclass.GSC,
        data: {
            order: 7,
            token: 'G00007',
        },
        start_time: '2000-01-01T00:00:00+08:00',
        end_time: '2099-01-01T00:00:00+08:00',
        state: TournamentState.Normal,
    });
}

function gscParticipantList(participant: boolean) {
    if (!participant) return [];
    return [{
        id: 701,
        token: 'G00007',
        arbiter_identifier__identifier: 'Player G00007',
        tournament_id: tournamentId,
        user_id: 99,
        start_time: '2000-01-01T00:00:00+08:00',
        end_time: '2099-01-01T00:00:00+08:00',
        rank: null,
        rank_score: 0,
    }];
}

function mountGSC(options: {
    loginStatus: LoginStatus;
    participant: boolean;
    realname?: string;
    tournament?: Tournament;
}) {
    const tournament = options.tournament ?? gscTournament();
    store.login_status = options.loginStatus;
    if (options.loginStatus === LoginStatus.IsLogin) {
        store.login({ id: 99, username: 'player', realname: options.realname ?? 'Player' });
    } else {
        store.logout();
        store.login_status = options.loginStatus;
    }

    cy.intercept('GET', '**/api/tournament/participants*', {
        body: gscParticipantList(options.participant).map((participant) => (tournament.getDisplayState() === TournamentState.Preparing
            ? { ...participant, token: '', arbiter_identifier__identifier: null, start_time: tournament.startDate?.toISOString() }
            : participant)),
    }).as('participantList');
    cy.intercept('GET', '**/api/tournament/get_videos/participant*', {
        body: [],
    }).as('participantVideos');

    cy.mount(App, {
        props: {
            tournament,
        },
        global: {
            plugins: [pinia, i18n, hashRouter()],
            config: {
                globalProperties: {
                    $axios,
                },
            },
        },
    });
    cy.wait('@participantList').its('response.statusCode').should('eq', 200);
}

describe('<GSC App />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        cy.mockPlayerNameFallback();
    });

    it('uses stored manual scores in a site participant summary even when no replays exist', () => {
        const tournament = gscTournament();
        tournament.state = TournamentState.Awarded;
        const row = { id: 701, user_id: 987654, manual_scores: true, arbiter_identifier: null, has_videos: false, rank: 1, rank_score: 0, bt1st: 1000, bt20th: 2000, bt20sum: 3000, it1st: 4000, it12th: 5000, it12sum: 6000, et1st: 7000, et5th: 8000, et5sum: 9000 };
        cy.intercept('GET', '**/api/tournament/gsc/results*', { body: [row] }).as('results');
        cy.intercept('GET', '**/api/tournament/get_videos/participant*', { body: [] }).as('manualVideos');
        store.logout();
        cy.mount(App, { props: { tournament }, global: { plugins: [pinia, i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait('@results');
        cy.get('.el-table__body tbody tr').first().find('td').eq(1).click();
        cy.wait('@manualVideos');
        cy.get('[data-cy=manual-personal-summary] .el-table__body').extractTableData().should((rows) => {
            expect(rows[0].slice(1)).to.deep.equal(['1.000', '2.000', '3.000', '4.000', '5.000', '6.000', '7.000', '8.000', '9.000', '12.000', '15.000', '18.000']);
        });
    });
    it('hides real-time score for anonymous users during ongoing tournament', () => {
        mountGSC({ loginStatus: LoginStatus.NotLogin, participant: false });
        cy.get('a.link[href$="/guide/gsc"]').should('be.visible');

        cy.contains('Ongoing').should('be.visible');
        cy.contains('Real-Time Score').should('not.exist');
        cy.get('.auto-uploader').should('not.exist');
    });

    it('hides real-time score for logged-in users before registration', () => {
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: false });

        cy.contains('Ongoing').should('be.visible');
        cy.contains('Real-Time Score').should('not.exist');
        cy.get('.auto-uploader').should('not.exist');
    });

    it('disables registration for logged-in users without real name', () => {
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: false, realname: '' });
        cy.intercept('POST', '**/api/tournament/gsc/participant', { statusCode: 200, body: {} }).as('createGSCParticipant');

        cy.contains('button', 'Register').should('be.disabled');
        cy.contains('Real name or player verification required').should('be.visible');
        cy.contains('Real-Time Score').should('not.exist');
        cy.get('@createGSCParticipant.all').should('have.length', 0);
    });

    it('shows real-time score for registered users', () => {
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: true });

        cy.contains('Real-Time Score').should('be.visible');
        cy.wait('@participantVideos').its('response.statusCode').should('eq', 200);
        cy.get('.auto-uploader').should('be.visible');
    });

    it('registers before start without revealing a token or opening Arbiter registration', () => {
        const tournament = gscTournament();
        tournament.startDate = new Date('2098-01-01T00:00:00Z');
        tournament.data = { order: 7, token: '' };
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: false, tournament });
        cy.intercept('POST', '**/api/tournament/gsc/participant', { body: { type: 'success' } }).as('register');
        cy.intercept('GET', '**/api/tournament/participants*', {
            body: gscParticipantList(true).map((participant) => ({ ...participant, token: '', arbiter_identifier__identifier: null })),
        }).as('registeredList');
        cy.contains('button', 'Register').should('be.enabled').click();
        cy.wait('@register');
        cy.wait('@registeredList');
        cy.contains('Registered. The tournament token').should('be.visible');
        cy.contains('[data-cy=gsc-participants] .el-tag', 'User#99').should('be.visible');
        cy.contains('G00007').should('not.exist');
        cy.get('.el-input input').should('not.exist');
        cy.get('#tab-personal').should('not.exist');
        cy.get('@participantVideos.all').should('have.length', 0);
    });

    it('renders player tags with Arbiter identifiers but no token, interval or deletion controls', () => {
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: true });
        cy.get('[data-cy=gsc-participants]').within(() => {
            cy.get('.el-tag').should('have.length', 1).and('contain.text', 'User#99').and('contain.text', 'Player G00007');
            cy.contains('User#701').should('not.exist');
            cy.contains('2000-01-01').should('not.exist');
            cy.get('button, .el-table, .ttfamily').should('not.exist');
        });
        cy.get('[data-cy=delete-participant]').should('not.exist');
    });

    it('applies the inline GSC filters to parsed identifiers, modes, levels and BV', () => {
        mountGSC({ loginStatus: LoginStatus.IsLogin, participant: true });
        cy.wait('@participantVideos');
        cy.get('.auto-uploader select[aria-label="Filter"]').should('have.value', 'supported');
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const filter: (video: AutoUploadVideo) => boolean = wrapper.findComponent<typeof AutoUploader>('.auto-uploader').props('filter');
            ['tournament', 'supported', 'bv'].forEach((filterLevel, stage) => {
                cy.get('.auto-uploader select[aria-label="Filter"]').select(filterLevel);
                cy.then(() => {
                    const video: AutoUploadVideo = { filename: 'test.evf', identifier: '', tokens: ['G00007'], stat: new VideoAbstract({ level: 'e', mode: MS_Mode.Standard, timems: 40000, bv: 100, software: 'e' }) };
                    expect(filter(video)).to.equal(true);
                    expect(filter({ ...video, tokens: ['G00007X'] })).to.equal(false);
                    video.stat.mode = MS_Mode.SpeedNG;
                    expect(filter(video)).to.equal(stage === 0);
                    video.stat.mode = MS_Mode.Standard;
                    video.stat.right_ce = 0;
                    video.stat.level = new VideoAbstract({ level: 'c10_10_10', mode: MS_Mode.Standard, timems: 1000, bv: 10, software: 'e' }).level;
                    expect(filter(video)).to.equal(stage === 0);
                    video.stat.level = 'e';
                    video.stat.bv = 99;
                    expect(filter(video)).to.equal(stage < 2);
                    video.stat.bv = 100;
                    video.stat.software = 'a';
                    expect(filter(video)).to.equal(false);
                    expect(filter({ ...video, identifier: 'Player G00007', tokens: [] })).to.equal(true);
                    expect(filter({ ...video, identifier: 'Player G00007 ' })).to.equal(false);
                });
            });
        });
    });
});
