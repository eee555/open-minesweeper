import App from './App.vue';

import i18n from '@/i18n';
import { fetchVideoInfo } from '@/services/videoInfoService';
import { videoplayerstore } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';
import { mockVideoInfo } from '@cy/support/videoInfo';

describe('Video player dialog', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        mockVideoInfo([
            { id: 42, identifier: 'Arbiter 玩家', tournament_identifier: ['GSC 2026', 'Round 2'] },
            { id: 43, identifier: '', tournament_identifier: [] },
        ]);
        videoplayerstore.id = 42;
        videoplayerstore.visible = true;
    });

    afterEach(() => {
        videoplayerstore.visible = false;
    });

    it('shows cached identifiers in the title and closes when following the analyzer link', () => {
        cy.then(() => fetchVideoInfo(42));
        const router = hashRouter({ initialPath: '/' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(App, { global: { plugins: [i18n, router], stubs: { NativePlayer: true } } });
        });
        cy.get('.video-player__identifier .identifier-text').should('have.text', 'Arbiter 玩家');
        cy.get('.video-player__tournament-identifier .identifier-text').should('have.length', 2).then(($identifiers) => {
            expect(Array.from($identifiers, (element) => element.textContent)).to.deep.equal(['GSC 2026', 'Round 2']);
        });
        cy.get('@parsedVideoInfo.all').should('have.length', 1);
        cy.get('.video-player__analyzer-link').should('have.attr', 'href', '#/video/42').and('contain.text', '#42').click();
        cy.hash().should('eq', '#/video/42');
        cy.wrap(videoplayerstore).its('visible').should('eq', false);
        cy.shouldBeAbsentOrHidden('.el-dialog');
    });

    it('clears previous identifiers when switching to a replay with no identifiers', () => {
        cy.mount(App, { global: { plugins: [i18n, hashRouter()], stubs: { NativePlayer: true } } });
        cy.wait('@parsedVideoInfo').its('request.query.ids').should('eq', '42');
        cy.get('.video-player__identifier .identifier-text').should('have.text', 'Arbiter 玩家');
        cy.then(() => {
            videoplayerstore.id = 43;
        });
        cy.wait('@parsedVideoInfo').its('request.query.ids').should('eq', '43');
        cy.get('.video-player__analyzer-link').should('have.attr', 'href', '#/video/43');
        cy.get('.video-player__identifier').should('have.text', '—');
        cy.get('.video-player__tournament-identifier').should('have.text', '—');
        cy.get('.video-player__identifiers .identifier-text').should('not.exist');
    });
});
