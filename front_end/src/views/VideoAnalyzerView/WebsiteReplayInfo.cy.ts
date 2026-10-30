import { h, ref } from 'vue';

import analyzerVersion from '../../../local-analyzer/version.json';

import type { SiteReplayInfo } from './useSiteReplayInfo';
import WebsiteReplayInfo from './WebsiteReplayInfo.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { utc_to_local_format } from '@/utils/system/tools';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const offlineDownloadFilename = `OpenMinesweeperVideoAnalyzer-${analyzerVersion.version}.zip`;

function fixture(): SiteReplayInfo {
    return { video: { id: 42, player: 7, upload_time: '2026-10-12T10:00:00Z' }, expanded_video: {}, tournament_ids: [2, 3], filename: '原始录像.evf', rankings: [{ ranking: 'saolei', stat: 'bt', nf: false, rank: 3 }, { ranking: 'pb', stat: 'time', nf: true, rank: 5 }] };
}

describe('<WebsiteReplayInfo />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        cy.mockPlayerNameFallback();
    });

    it('shows four ordered rows with upload time, PlayerName, all tournament links, video ranks and original filename', () => {
        const info = fixture();
        cy.mount(WebsiteReplayInfo, { props: { id: '42', info }, global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.get('.website-replay-info__row').should('have.length', 4);
        cy.get('.website-replay-info__row').eq(0).should('contain.text', '#42').and('contain.text', utc_to_local_format(info.video.upload_time));
        cy.get('.website-replay-info__row').eq(1).find('a[href="#/player/7"]').should('exist');
        cy.get('.website-replay-info__tournaments a').should('have.length', 2);
        cy.get('.website-replay-info__tournaments a').first().should('have.attr', 'href', '#/tournament/2');
        cy.get('.website-replay-info__row').eq(2).should('contain.text', '#3').and('contain.text', '#5');
        cy.get('.website-replay-info__row').eq(3).should(($row) => {
            expect($row.text().trim()).to.eq(info.filename);
        });
        cy.get('.website-replay-info__links a').should('have.length', 1);
        cy.get('.website-replay-info__links button').should('have.length', 1);
        cy.get('.website-replay-info__replay-download').should('be.visible').and('not.be.disabled').and('have.attr', 'aria-label', 'Download replay file');
        cy.get('.website-replay-info__replay-download .pi-file-export').should('be.visible');
        cy.get('.website-replay-info__offline-download').should('be.visible').and('have.attr', 'download', offlineDownloadFilename).and('have.attr', 'href', `${import.meta.env.BASE_URL}assets/${offlineDownloadFilename}`).and('have.attr', 'aria-label', 'Download offline package').and('have.attr', 'title', 'Download offline package');
        cy.get<HTMLImageElement>('.website-replay-info__offline-download img').should('be.visible').and('have.attr', 'alt', '').and(($icon) => {
            expect($icon[0].complete).to.eq(true);
            expect($icon[0].naturalWidth).to.be.greaterThan(0);
            expect($icon[0].getBoundingClientRect().width).to.eq(16);
        });
        cy.get('.website-replay-info').should(($info) => {
            const details = $info.find('.website-replay-info__details')[0].getBoundingClientRect();
            const links = $info.find('.website-replay-info__links')[0].getBoundingClientRect();
            expect(links.left).to.be.greaterThan(details.right);
            expect(links.top).to.be.closeTo(details.top, 1);
        });
    });

    it('omits absent tournament links, distinguishes unranked and failed requests, and wraps a long filename in a narrow container', () => {
        const state = ref<SiteReplayInfo | null>({ ...fixture(), tournament_ids: [], rankings: [], filename: `${'长文件名'.repeat(30)}.evf` });
        const errorMessage = ref('');
        cy.mount({ render: () => h('div', { style: { width: '240px' } }, [h(WebsiteReplayInfo, { id: '42', info: state.value, errorMessage: errorMessage.value })]) }, { global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.get('.website-replay-info__tournaments').should('not.exist');
        cy.get('.website-replay-info__rankings').should('contain.text', 'Not ranked');
        cy.get('.website-replay-info__filename').should(($filename) => {
            expect($filename[0].scrollWidth).to.be.at.most($filename[0].clientWidth + 1);
        });
        cy.get('.website-replay-info').should(($info) => {
            expect($info[0].scrollWidth).to.be.at.most($info[0].clientWidth + 1);
        });
        cy.then(() => {
            state.value = null;
            errorMessage.value = '403 Forbidden';
        });
        cy.get('.website-replay-info [role="alert"]').should('contain.text', '403 Forbidden');
        cy.get('.website-replay-info__replay-download').should('be.visible').and('not.be.disabled').and('have.attr', 'aria-label', 'Download replay file');
        cy.get('.website-replay-info__offline-download').should('be.visible').and('not.have.attr', 'aria-disabled');
        cy.get('.website-replay-info__player a').should('not.exist');
        cy.get('.website-replay-info__filename').should(($filename) => {
            expect($filename.text().trim()).to.eq('--');
        });
    });

    it('keeps the replay download available while website information is loading', () => {
        cy.mount(WebsiteReplayInfo, { props: { id: '42', loading: true }, global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.get('.website-replay-info__rankings').should('contain.text', 'Loading website information');
        cy.get('.website-replay-info__replay-download').should('be.visible').and('not.be.disabled').and('have.attr', 'aria-label', 'Download replay file');
    });
});
