import MediaListPanel from './MediaListPanel.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const mediaItem = {
    id: 7,
    title: 'Work',
    language: 'en',
    created_at: '2026-01-01T00:00:00Z',
    submitted_at: '2026-01-01T00:00:00Z',
    format: 'B_v',
    status: 'verified',
    rejected_at: null,
    reject_reason: '',
    refunded_likes: 0,
    likes: 3,
    hot_value: 3.1,
    hot_value_updated_at: '2026-01-01T00:00:00Z',
    metadata_pending: false,
    user_id: 42,
    rejected_by: null,
    url: 'https://www.bilibili.com/video/BV1xx411c7mD/',
    embed_url: null,
    hot_now: 3,
};

const rankingBody = {
    items: [mediaItem],
    total: 1,
    start: 0,
    anchor: new Date().toISOString(),
};

describe('<MediaListPanel />', () => {
    installHashHistoryCleanup();

    it('keeps feeding enabled when only submissions are banned', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, { body: rankingBody }).as('ranking');
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, {
            body: { balance: 5, likes_sent: 0, banned: true },
        }).as('me');
        const router = hashRouter({ initialPath: '/works' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(MediaListPanel, {
                props: { source: 'ranking' },
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@me');
        cy.wait('@ranking');
        cy.get('.media-card button.media-text-button').should('not.be.disabled');
    });

    it('reloads /me after an in-page login', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, { body: rankingBody });
        let calls = 0;
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, (request) => {
            calls += 1;
            request.reply({ body: { balance: calls === 1 ? 5 : 42, likes_sent: 0, banned: false } });
        }).as('me');
        const router = hashRouter({ initialPath: '/works' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(MediaListPanel, {
                props: { source: 'ranking' },
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@me');
        cy.get('.media-card button.media-text-button').should('have.attr', 'title').and('contain', '5');
        cy.then(() => {
            store.sessionRevision += 1;
        });
        cy.wait('@me');
        cy.get('.media-card button.media-text-button').should('have.attr', 'title').and('contain', '42');
    });
});
