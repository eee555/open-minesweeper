import { h } from 'vue';
import type { RouteRecordRaw } from 'vue-router';
import { RouterLink, RouterView } from 'vue-router';

import VideoPlayer from './App.vue';

import PlayerName from '@/components/PlayerName.vue';
import $axios from '@/http';
import i18n from '@/i18n';
import { videoplayerstore } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

function Page(label: string) {
    return { render: () => h('div', { 'data-cy': 'page' }, label) };
}

function navigationRoutes(): RouteRecordRaw[] {
    return [
        { path: '/ranking', redirect: '/ranking/speed' },
        { path: '/ranking/speed', component: Page('ranking') },
        { path: '/player/:id', redirect: (to) => `/player/${String(to.params.id)}/top` },
        { path: '/player/:id/top', component: Page('player') },
        { path: '/video/:id', component: Page('video') },
    ];
}

function mountNavigation(initialPath: string) {
    const router = hashRouter({ routes: navigationRoutes(), initialPath });
    cy.wrap(router.isReady()).then(() => {
        cy.mount({
            render: () => h('div', [
                h(RouterLink, { to: '/ranking', 'data-cy': 'nav-ranking', style: 'position: fixed; z-index: 10000; top: 8px; right: 8px;' }, { default: () => 'Ranking' }),
                h(PlayerName, { userId: 42 }),
                h(VideoPlayer),
                h(RouterView),
            ]),
        }, {
            global: {
                plugins: [i18n, router],
                config: { globalProperties: { $axios } },
                stubs: { NativePlayer: true },
            },
        });
    });
}

describe('hash navigation after opening a replay', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        videoplayerstore.visible = false;
        cy.mockPlayerNameFallback();
    });

    afterEach(() => {
        videoplayerstore.visible = false;
    });

    it('updates the view after a username, replay title and ranking click', () => {
        mountNavigation('/ranking');

        cy.get('[data-cy=page]').should('have.text', 'ranking');
        cy.contains('a', 'User#42').click();
        cy.get('[data-cy=page]').should('have.text', 'player');
        cy.hash().should('eq', '#/player/42/top');

        cy.then(() => {
            videoplayerstore.id = 42;
            videoplayerstore.visible = true;
        });
        cy.get('.video-player__analyzer-link').should('have.attr', 'href', '#/video/42').click();
        cy.get('[data-cy=page]').should('have.text', 'video');
        cy.hash().should('eq', '#/video/42');
        cy.window().its('history.state.current').should('eq', '/video/42');
        cy.wrap(videoplayerstore).its('visible').should('eq', false);

        cy.get('[data-cy=nav-ranking]').click();
        cy.hash().should('eq', '#/ranking/speed');
        cy.get('[data-cy=page]').should('have.text', 'ranking');
    });

    it('closes the preview when ranking navigation changes the route', () => {
        mountNavigation('/player/42/top');
        cy.get('[data-cy=page]').should('have.text', 'player');
        cy.then(() => {
            videoplayerstore.id = 42;
            videoplayerstore.visible = true;
        });
        cy.get('.el-dialog').should('be.visible');
        cy.get('.video-player__analyzer-link').should('be.visible').and('have.attr', 'href', '#/video/42');
        cy.get('[data-cy=nav-ranking]').should('have.attr', 'href', '#/ranking').click();
        cy.hash().should('eq', '#/ranking/speed');
        cy.get('[data-cy=page]').should('have.text', 'ranking');
        cy.wrap(videoplayerstore).its('visible').should('eq', false);
        cy.shouldBeAbsentOrHidden('.el-dialog');
    });
});
