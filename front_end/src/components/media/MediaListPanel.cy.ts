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

const pageBody = {
    items: [mediaItem],
    total: 1,
    start: 0,
    anchor: new Date().toISOString(),
};

describe('<MediaListPanel />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, { body: pageBody }).as('ranking');
        cy.intercept({ method: 'GET', pathname: '/api/media/latest' }, { body: pageBody }).as('latest');
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, {
            body: { balance: 5, likes_sent: 0, banned: true },
        }).as('me');
    });

    function mountPanel() {
        const router = hashRouter({ initialPath: '/works' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(MediaListPanel, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
    }

    it('renders the five columns and keeps feeding enabled when only submissions are banned', () => {
        mountPanel();
        cy.wait('@me');
        cy.wait('@ranking');
        cy.get('.base-table thead th').should('have.length', 5);
        cy.get('[data-sort=hot]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=media-row-7] [data-cy=media-title-link]').should('have.attr', 'href', mediaItem.url);
        cy.get('[data-cy=media-row-7] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://www.bilibili.com/favicon.ico').
            and('have.attr', 'alt', 'Bilibili');
        cy.get('[data-cy=media-row-7]').should('contain.text', '3.00').and('contain.text', '3');
        cy.get('[data-cy=media-row-7] button.media-text-button').should('not.be.disabled').
            and('have.attr', 'title').and('contain', '5');
    });

    it('shows the platform icon matching the media format', () => {
        const saoleiWork = { ...mediaItem, id: 9, format: 'c_p', title: 'Saolei post', url: 'https://saolei.wang/bbs/9786' };
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, {
            body: { ...pageBody, items: [mediaItem, saoleiWork], total: 2 },
        });
        mountPanel();
        cy.get('[data-cy=media-row-7] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://www.bilibili.com/favicon.ico');
        cy.get('[data-cy=media-row-9] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://saolei.wang/icon.svg').
            and('have.attr', 'alt', 'Saolei.wang');
    });

    it('switches the backend sort through the table headers', () => {
        mountPanel();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'hot');
        cy.get('[data-sort=latest]').click();
        cy.wait('@latest');
        cy.get('[data-sort=latest]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-sort=likes]').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'likes');
        cy.get('[data-sort=hot]').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'hot');
    });

    it('opens a preview dialog for embeddable works instead of following the external link', () => {
        const embeddable = {
            ...mediaItem,
            id: 8,
            title: 'Embeddable work',
            embed_url: 'https://player.bilibili.com/player.html?bvid=BV1xx411c7mD',
        };
        cy.intercept({ method: 'GET', pathname: '/api/media/ranking' }, {
            body: { ...pageBody, items: [mediaItem, embeddable], total: 2 },
        });
        mountPanel();
        cy.get('[data-cy=media-row-7] [data-cy=media-title-link]').should('have.attr', 'href', mediaItem.url);
        cy.get('[data-cy=media-row-8] [data-cy=media-title-link]').should('not.exist');
        cy.get('[data-cy=media-row-8] [data-cy=media-preview-link]').should('contain.text', 'Embeddable work').click();
        cy.get('.el-dialog:visible iframe.media-preview-frame').should('have.attr', 'src', embeddable.embed_url);
        cy.get('.el-dialog:visible a.media-preview-external').should('have.attr', 'href', mediaItem.url);
    });

    it('reloads /me after an in-page login', () => {
        let calls = 0;
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, (request) => {
            calls += 1;
            request.reply({ body: { balance: calls === 1 ? 5 : 42, likes_sent: 0, banned: false } });
        }).as('meSequence');
        mountPanel();
        cy.wait('@meSequence');
        cy.get('[data-cy=media-row-7] button.media-text-button').should('have.attr', 'title').and('contain', '5');
        cy.then(() => {
            store.sessionRevision += 1;
        });
        cy.wait('@meSequence');
        cy.get('[data-cy=media-row-7] button.media-text-button').should('have.attr', 'title').and('contain', '42');
    });
});
