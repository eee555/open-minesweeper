import type AutoUploader from '../common/AutoUploader.vue';
import type { AutoUploadVideo } from '../common/utils';

import App from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { MS_Mode, MS_State, TournamentState, TournamentSubclass } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';
import { VideoAbstract } from '@/utils/videoabstract';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<Efficiency Weekly App />', () => {
    installHashHistoryCleanup();

    it('uses the efficiency registration response and metric-based automatic upload filters', () => {
        cy.mockPlayerNameFallback();
        store.login({ id: 99, username: 'eff-player', realname: 'Player' });
        const tournament = new Tournament({ id: 8, host_id: 100, subclass: TournamentSubclass.WeeklyEff, data: { year: 2099, week: 8 }, state: TournamentState.Normal, start_time: '2000-01-01T00:00:00Z', end_time: '2099-01-01T00:00:00Z' });
        cy.intercept('GET', '**/api/tournament/participants*', { body: [] }).as('participants');
        cy.intercept('POST', '**/api/tournament/weekly-eff/participant', { body: { id: 801, user_id: 99, token: 'EFF-TOKEN', tournament_id: 8, start_time: '2026-01-01T00:00:00Z', end_time: '2099-01-01T00:00:00Z', rank: null, rank_score: 0, has_videos: false } }).as('register');
        cy.intercept('GET', '**/api/tournament/get_videos/participant*', { body: [{ id: 1, software: 'e', level: 'i', mode: MS_Mode.Standard, state: MS_State.Official, timems: 40000, cl: 3, bv: 6 }] }).as('videos');
        cy.mount(App, { props: { tournament }, global: { plugins: [pinia, i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait('@participants');
        cy.contains('button', 'Start my session').click();
        cy.contains('.el-dialog button', 'Confirm').click();
        cy.wait('@register');
        cy.wait('@videos');
        cy.get('@participants.all').should('have.length', 1);
        cy.get('.auto-uploader select').should('have.value', 'supported');
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const filter: (video: AutoUploadVideo) => boolean = wrapper.findComponent<typeof AutoUploader>('.auto-uploader').props('filter');
            const replay: AutoUploadVideo = { filename: 'eff.evf', identifier: '', tokens: ['EFF-TOKEN'], stat: new VideoAbstract({ level: 'i', mode: MS_Mode.Standard, timems: 90000, cl: 3, bv: 6, software: 'e', state: MS_State.Official }) };
            expect(filter(replay)).to.equal(true);
            expect(filter({ ...replay, tokens: ['OTHER'] })).to.equal(false);
            cy.get('.auto-uploader select').select('scoreRefreshing');
            cy.then(() => {
                expect(filter(replay)).to.equal(true);
                replay.stat.timems = 120000;
                expect(filter(replay)).to.equal(false);
            });
            cy.get('.auto-uploader select').select('supported');
            cy.then(() => {
                replay.stat.timems = 120000;
                expect(filter(replay)).to.equal(false);
                replay.stat.mode = MS_Mode.SpeedNG;
                expect(filter(replay)).to.equal(false);
            });
        });
    });
});
