import { QuestionFilled } from '@element-plus/icons-vue';
import { defineComponent, h, reactive } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import UserVideoView from './UserVideoView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { activityCalendarConfig, BBBvSummaryConfig, store, VideoListConfig } from '@/store';
import { pinia } from '@/store/create';
import { MS_Mode } from '@/utils/ms_const';
import { UserProfile } from '@/utils/userprofile';
import type { VideoAbstract } from '@/utils/videoabstract';
import { mockVideoInfo } from '@cy/support/videoInfo';

const VIDEO_TABLE = '[data-cy=video-list-table] table';

const ScatterStub = defineComponent({
    props: { videos: { type: Array<VideoAbstract>, default: () => [] } },
    setup: (props) => () => h('div', { 'data-cy': 'scatter-videos' }, props.videos.map((video) => video.id).join(',')),
});

function mountUserVideos(userId = 99, hiddenStates = [true, false], overrides: Record<string, unknown>[] = []) {
    store.login({ id: 99, username: 'player', realname: 'Player' });
    VideoListConfig.value.profile = ['time'];
    BBBvSummaryConfig.value.softwareFilter = ['e', 'a', 'r', 'm'];
    BBBvSummaryConfig.value.template = 'time';
    activityCalendarConfig.value.useEndTime = false;
    const user = reactive(new UserProfile({ id: userId }));
    cy.intercept('GET', '**/api/userprofile/videolist*', {
        body: mockVideoInfo(hiddenStates.map((hidden, index) => ({
            id: 101 + index,
            level: 'e',
            mode: MS_Mode.Standard,
            software: 'e',
            timems: 40000,
            bv: 100,
            ongoing_tournament: hidden,
            upload_time: new Date(2026, 9, 14, 12).toISOString(),
            ...overrides[index],
        }))),
    }).as('videos');
    cy.intercept('GET', '**/api/video/preview*', { statusCode: 404 }).as('preview');
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/player/:id/videos', name: 'user-videos', component: UserVideoView }] });
    void router.push(`/player/${userId}/videos`);
    cy.wrap(router.isReady()).then(() => {
        cy.mount(UserVideoView, {
            props: { user },
            global: { plugins: [pinia, i18n, router], components: { QuestionFilled }, stubs: { VideoScatter: ScatterStub }, config: { globalProperties: { $axios } } },
        });
    });
    cy.wait('@videos');
    // VideoList loads its data columns asynchronously, after rows may already exist.
    cy.get(VIDEO_TABLE).contains('Time');
    if (userId === 99) cy.get(VIDEO_TABLE).contains('Action');
    cy.get(VIDEO_TABLE).extractTableData().should('deep.equal', [
        userId === 99 ? ['Time', 'Action'] : ['Time'],
        ...hiddenStates.slice(0, 25).map(() => (userId === 99 ? ['40.000', ''] : ['40.000'])),
    ]);
    return user;
}

function openActions(videoId: number) {
    cy.get(`[data-cy=video-row-actions][data-video-id="${videoId}"]`).click();
    cy.get('[data-tippy-root] [data-cy=reveal-video]:visible').should('be.visible');
}

describe('<UserVideoView />', () => {
    it('merges local CSV rows into the existing table, clears before failed imports and preserves server data', () => {
        const user = mountUserVideos();
        cy.get('[data-cy=arbiter-csv-upload] input[type=file]').should('not.exist');
        cy.get('[data-cy=toggle-arbiter-csv]').should('have.attr', 'aria-expanded', 'false').click();
        cy.get('[data-cy=toggle-arbiter-csv]').should('have.attr', 'aria-expanded', 'true');
        cy.then(() => {
            VideoListConfig.value.profile = ['state', 'time', 'bv', 'upload_time', 'file_size'];
        });
        cy.fixture('stats_csv.csv', 'utf8').then((csv: string) => {
            const lines = csv.trim().split(/\r?\n/);
            const contents = Cypress.Buffer.from([...lines, lines[1].replace(/^5,/, '6,')].join('\n'));
            cy.get('[data-cy=arbiter-csv-upload] input[type=file]').selectFile({ contents, fileName: 'stats.csv' }, { force: true });
        });
        cy.get('[data-cy=arbiter-csv-result]').should('contain.text', '2 local videos not uploaded');
        cy.get('[data-cy=toggle-arbiter-csv]').click();
        cy.get('[data-cy=arbiter-csv-upload] input[type=file]').should('not.exist');
        cy.get('[data-cy=local-video-state]').should('have.length', 2);
        cy.get('[data-cy=toggle-arbiter-csv]').click();
        cy.get('[data-cy=arbiter-csv-result]').should('contain.text', '2 local videos not uploaded');
        cy.get(VIDEO_TABLE).getTable().should('have.length', 4);
        cy.get(VIDEO_TABLE).contains('td', '35.090').click();
        cy.get(VIDEO_TABLE).contains('tr', '35.090').within(() => {
            cy.get('a, [data-cy=video-row-actions]').should('not.exist');
            cy.get('td').filter(':contains("—")').should('have.length', 2);
        });
        cy.get('@preview.all').should('have.length', 0);
        cy.get('[data-cy=video-shared-filters]').should('not.exist');
        cy.get('[data-cy=video-filter-state]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-menu]:visible input[value=l]').should('be.checked').uncheck();
        cy.get('[data-cy=local-video-state]').should('not.exist');
        cy.get('[data-tippy-root] [data-cy=video-filter-menu]:visible input[value=l]').check();
        cy.get('[data-cy=video-filter-state]').click();
        cy.get('[data-cy=arbiter-csv-upload] input[type=file]').selectFile({ contents: Cypress.Buffer.from('bad'), fileName: 'bad.csv' }, { force: true });
        cy.get('[data-cy=local-video-state]').should('not.exist');
        cy.get('[role=alert]').should('contain.text', 'Missing date or Time headers');
        cy.get('[data-cy=arbiter-csv-upload] input[type=file]').selectFile('cypress/fixtures/stats_csv.csv', { force: true });
        cy.get('[data-cy=local-video-state]').should('have.length', 1);
        cy.get('[data-cy=clear-arbiter-csv]').click();
        cy.get('[data-cy=local-video-state]').should('not.exist');
        cy.then(() => {
            expect(user.videos?.map((video) => video.id)).to.deep.equal([101, 102]);
        });
        cy.get('@videos.all').should('have.length', 1);
    });

    it('keeps BV display filters independent while sharing selection and filters with the scatter plot', () => {
        mountUserVideos(100, [false, false, false, false], [{ software: 'a' }, { software: 'r' }, { level: 'i' }, { bv: 101 }]);
        cy.then(() => {
            VideoListConfig.value.profile = ['state', 'software', 'time'];
        });
        cy.get('[data-cy=video-overview]').select('bv');
        cy.then(() => {
            BBBvSummaryConfig.value.softwareFilter = ['a'];
        });
        cy.get('button[aria-label="Expert BV 100"]').click();
        cy.get('button[aria-label="Expert BV 100"]').should('have.attr', 'aria-pressed', 'true');
        cy.get('button[aria-label="Intermediate BV 100"]').should('have.attr', 'aria-pressed', 'false');
        cy.get('[data-cy=video-range]').should('contain.text', '2 videos in range, 2 after filtering');
        cy.get(VIDEO_TABLE).getTable().should('have.length', 2);
        cy.get('[data-cy=video-shared-filters]').should('not.exist');
        cy.get('[data-cy=video-filter-software]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-menu]:visible [role=group][aria-label="Software"] input[value=a]').should('have.length', 1).uncheck();
        cy.get('[data-cy=video-filter-state]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-menu]:visible [role=group][aria-label="State"] input[value=a]').should('be.checked');
        cy.get('[data-cy=video-range]').should('contain.text', '2 videos in range, 1 after filtering');
        cy.get('[data-cy=video-presentation]').select('scatter');
        cy.get('[data-cy=video-shared-filters]').should('exist');
        cy.get('[data-cy=scatter-videos]').should('have.text', '102');
        cy.then(() => {
            BBBvSummaryConfig.value.softwareFilter = [];
        });
        cy.get('button[aria-label="Expert BV 100"]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=scatter-videos]').should('have.text', '102');
        cy.get('[data-cy=video-presentation]').select('table');
        cy.get(VIDEO_TABLE).getTable().should('have.length', 1);
        cy.get('button[aria-label="Expert BV 100"]').focus();
        cy.realPress('Enter');
        cy.get('[data-cy=video-range]').should('contain.text', '4 videos in range, 3 after filtering');
        cy.get('@videos.all').should('have.length', 1);
        cy.get('@preview.all').should('have.length', 0);
        cy.get('.el-dialog:visible').should('not.exist');
    });

    it('selects calendar days and cancels a repeated selection without reloading', () => {
        mountUserVideos(100, [false, false], [{}, { upload_time: new Date(2026, 9, 15, 12).toISOString() }]);
        cy.get('[data-cy=video-overview]').select('calendar');
        cy.get('[data-cy=cell-2026-10-14]').click();
        cy.get('[data-cy=cell-2026-10-14]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=video-range]').should('contain.text', '1 videos in range, 1 after filtering');
        cy.get('[data-cy=video-presentation]').select('scatter');
        cy.get('[data-cy=scatter-videos]').should('have.text', '101');
        cy.get('[data-cy=cell-2026-10-14]').focus();
        cy.realPress('Space');
        cy.get('[data-cy=cell-2026-10-14]').should('have.attr', 'aria-pressed', 'false');
        cy.get('[data-cy=scatter-videos]').should('have.text', '101,102');
        cy.get('[data-cy=cell-2026-10-13]').click();
        cy.get('[data-cy=cell-2026-10-13]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=video-range]').should('contain.text', '0 videos in range, 0 after filtering');
        cy.get('[data-cy=scatter-videos]').should('have.text', '');
        cy.get('[data-cy=video-overview]').select('none');
        cy.get('[data-cy=scatter-videos]').should('have.text', '101,102');
        cy.get('@videos.all').should('have.length', 1);
    });

    it('passes all filtered records to scatter regardless of the table page', () => {
        mountUserVideos(100, Array<boolean>(30).fill(false));
        cy.get(VIDEO_TABLE).getTable().should('have.length', 25);
        cy.get('[data-cy=video-presentation]').select('scatter');
        cy.get('[data-cy=scatter-videos]').should(($element) => {
            expect($element.text().split(',')).to.have.length(30);
        });
        cy.get('[data-cy=video-presentation]').select('table');
        cy.get(VIDEO_TABLE).getTable().should('have.length', 25);
        cy.get('@videos.all').should('have.length', 1);
    });

    it('updates columns through checkboxes and selected tag removal without refetching videos', () => {
        mountUserVideos(100, [false, false]);
        cy.get('button[aria-label="Select columns"]').click();
        cy.get('.checkbox-group input[value=bv]').should('not.be.checked');
        cy.get('.checkbox-group').contains('label', /^Bv$/).click();
        cy.get('.checkbox-group input[value=bv]').should('be.checked');
        cy.get(VIDEO_TABLE).contains('th', 'Bv').scrollIntoView();
        cy.get(VIDEO_TABLE).contains('th', 'Bv').should('be.visible');
        cy.contains('.el-tag', /^Time$/).find('.el-tag__close').click();
        cy.get('.checkbox-group input[value=time]').should('not.be.checked');
        cy.get(VIDEO_TABLE).contains('th', 'Time').should('not.exist');
        cy.wrap(VideoListConfig).its('value.profile').should('deep.equal', ['bv']);
        cy.get('@videos.all').should('have.length', 1);
    });

    it('opens actions in a popover, confirms reveal and updates only the selected video', () => {
        const user = mountUserVideos();
        cy.intercept('POST', '**/api/tournament/video/101/reveal', { statusCode: 204 }).as('reveal');
        cy.get('[data-cy=reveal-video]:visible').should('not.exist');
        openActions(101);
        cy.get('@preview.all').should('have.length', 0);
        cy.get('[data-cy=reveal-video]:visible').click();
        cy.contains('.el-dialog', 'It will still count in all its tournaments.').should('be.visible');
        cy.get('@reveal.all').should('have.length', 0);
        cy.contains('.el-dialog button', 'Cancel').click();
        openActions(101);
        cy.get('[data-cy=reveal-video]:visible').click();
        cy.contains('.el-dialog button', 'Confirm').click();
        cy.wait('@reveal');
        cy.contains('.el-dialog', 'It will still count in all its tournaments.').should('not.be.visible');
        cy.closeElNotifications();
        openActions(101);
        cy.get('[data-cy=reveal-video]:visible').should('be.disabled');
        cy.get('@videos.all').should('have.length', 1);
        cy.get('@preview.all').should('have.length', 0);
        cy.then(() => {
            expect(user.videos?.[0].ongoing_tournament).to.equal(false);
        });
    });

    it('keeps the video hidden on failure and allows retrying', () => {
        const user = mountUserVideos();
        cy.intercept('POST', '**/api/tournament/video/101/reveal', { statusCode: 403 }).as('reveal');
        openActions(101);
        cy.get('[data-cy=reveal-video]:visible').click();
        cy.contains('.el-dialog button', 'Confirm').click();
        cy.wait('@reveal');
        cy.get('.el-notification--error').should('be.visible');
        cy.closeElNotifications();
        cy.contains('.el-dialog button', 'Confirm').should('be.enabled').and('not.have.attr', 'aria-busy');
        cy.then(() => {
            expect(user.videos?.[0].ongoing_tournament).to.equal(true);
        });
    });

    it('shares one dialog between rows and reveals the last selected video', () => {
        const user = mountUserVideos(99, [true, true]);
        cy.intercept('POST', '**/api/tournament/video/102/reveal', { statusCode: 204 }).as('revealSecond');
        openActions(101);
        cy.get('[data-cy=reveal-video]:visible').click();
        cy.get('[data-cy=reveal-video]:visible').should('not.exist');
        cy.get('.el-dialog').should('have.length', 1);
        cy.contains('.el-dialog button', 'Cancel').click();
        openActions(102);
        cy.get('[data-cy=reveal-video]:visible').click();
        cy.get('[data-cy=reveal-video]:visible').should('not.exist');
        cy.get('.el-dialog').should('have.length', 1);
        cy.contains('.el-dialog button', 'Confirm').click();
        cy.wait('@revealSecond');
        cy.then(() => {
            expect(user.videos?.map((video) => video.ongoing_tournament)).to.deep.equal([true, false]);
        });
        cy.closeElNotifications();
    });

    it('disables revealing an already public video', () => {
        mountUserVideos();
        openActions(102);
        cy.get('[data-cy=reveal-video]:visible').should('be.disabled');
    });

    it('does not expose the actions column on another profile even for staff', () => {
        mountUserVideos(100, [false, false]);
        cy.then(() => {
            store.user.is_staff = true;
        });
        cy.get('[data-cy=video-row-actions]').should('not.exist');
        cy.contains('th', 'Action').should('not.exist');
        cy.get('[data-cy=arbiter-csv-upload] input[type=file]').should('not.exist');
        cy.get('[data-cy=toggle-arbiter-csv]').should('not.exist');
    });
});
