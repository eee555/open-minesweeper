import { defineComponent, h } from 'vue';

import MediaListPanel from './MediaListPanel.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { resetGitHubRepositoryCache } from '@/services/githubService';
import { store } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const mediaItem = {
    id: 7,
    title: 'Work',
    language: 'en',
    created_at: '2026-01-01T00:00:00Z',
    submitted_at: '2026-01-02T00:00:00Z',
    format: 'B_a',
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
    suffix: '1646742',
    hot_now: 3,
};

const pageBody = {
    items: [mediaItem],
    has_more: false,
    next_cursor: null,
};

describe('<MediaListPanel />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        resetGitHubRepositoryCache();
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, { body: pageBody }).as('ranking');
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, {
            body: { balance: 5, likes_sent: 0, banned: true, daily_likes_used: 3 },
        }).as('me');
    });

    function mountPanel() {
        const router = hashRouter({ initialPath: '/works' });
        cy.wrap(router.isReady()).then(() => {
            const ScrollPanel = defineComponent({ expose: [], render: () => h('main', { class: 'common-layout', style: { height: '220px', overflow: 'auto' } }, [h(MediaListPanel)]) });
            cy.mount(ScrollPanel, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
    }

    const firstBatch = Array.from({ length: 12 }, (_, index) => ({ ...mediaItem, id: index + 7 }));

    it('loads the next cursor at the bottom and deduplicates dynamic results', () => {
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, (request) => {
            request.reply({ body: request.query.cursor !== undefined
                ? { ...pageBody, items: [firstBatch[11], { ...mediaItem, id: 99 }] }
                : { ...pageBody, items: firstBatch, has_more: true, next_cursor: 'next-batch' } });
        }).as('pages');
        mountPanel();
        cy.wait('@pages').its('request.query.sort').should('equal', 'submitted');
        cy.get('.base-table tbody tr').should('have.length', 12);
        cy.get('main.common-layout').scrollTo('bottom');
        cy.wait('@pages').its('request.query').should('include', { cursor: 'next-batch' }).and('not.have.property', 'start');
        cy.get('.base-table tbody tr').should('have.length', 13);
        cy.get('[data-cy=works-end]').should('exist');
        cy.get('.el-pagination').should('not.exist');
        cy.get('[data-cy=works-time-sort-toggle]').click();
        cy.wait('@pages').its('request.query').should('include', { sort: 'latest' }).and('not.have.property', 'cursor');
        cy.get('.base-table tbody tr').should('have.length', 12);
    });

    it('keeps loaded rows and retries the same cursor after a failed append', () => {
        let attempts = 0;
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, (request) => {
            if (request.query.cursor === undefined) request.reply({ body: { ...pageBody, items: firstBatch, has_more: true, next_cursor: 'retry-cursor' } });
            else if (++attempts === 1) request.reply({ statusCode: 500 });
            else request.reply({ body: { ...pageBody, items: [{ ...mediaItem, id: 99 }] } });
        }).as('pages');
        mountPanel();
        cy.wait('@pages');
        cy.get('main.common-layout').scrollTo('bottom');
        cy.wait('@pages');
        cy.get('.base-table tbody tr').should('have.length', 12);
        cy.get('[data-cy=works-retry]').click();
        cy.wait('@pages').its('request.query.cursor').should('equal', 'retry-cursor');
        cy.get('.base-table tbody tr').should('have.length', 13);
    });

    it('applies type and language together and restarts the cursor when sorting', () => {
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, { body: pageBody }).as('filtered');
        mountPanel();
        cy.wait('@filtered');
        cy.get('[data-cy=works-format]').select('B_a');
        cy.get('[data-cy=works-language]').click();
        cy.get('.el-select-dropdown:visible .el-select-dropdown__item').should('have.length', 4);
        cy.get('.el-select-dropdown:visible').contains('.el-select-dropdown__item', 'Español').click();
        cy.get('[data-cy=works-apply-filters]').click();
        cy.wait('@filtered').its('request.query').should('include', { format: 'B_a', language: 'es', sort: 'submitted' }).and('not.have.property', 'cursor');
        cy.get('[data-cy=works-time-sort-toggle]').click();
        cy.wait('@filtered').its('request.query').should('include', { format: 'B_a', language: 'es', sort: 'latest' }).and('not.have.property', 'cursor');
        cy.get('[data-cy=works-language]').click();
        cy.get('.el-select-dropdown:visible').contains('.el-select-dropdown__item', 'Other').click();
        cy.get('[data-cy=works-apply-filters]').click();
        cy.wait('@filtered').its('request.query').should('include', { format: 'B_a', language: 'other', sort: 'latest' }).and('not.have.property', 'cursor');
        cy.get('[data-cy=works-clear-filters]').click();
        cy.wait('@filtered').then(({ request }) => {
            expect(request.query).not.to.have.property('format');
            expect(request.query).not.to.have.property('language');
        });
    });

    it('renders the five columns and keeps feeding enabled when only submissions are banned', () => {
        mountPanel();
        cy.wait('@me');
        cy.wait('@ranking');
        cy.get('.base-table thead th').should('have.length', 5);
        cy.get('[data-sort=submitted]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy=media-row-7] [data-cy=media-title-link]').should('have.attr', 'href', 'https://www.bilibili.com/read/cv1646742');
        cy.get('[data-cy=media-row-7] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://www.bilibili.com/favicon.ico').
            and('have.attr', 'alt', 'Bilibili');
        cy.get('[data-cy=media-row-7]').should('contain.text', '3.00').and('contain.text', '3');
        cy.get('[data-cy=media-row-7] button.media-text-button').should('not.be.disabled').
            and('have.attr', 'title').and('contain', '5');
    });

    it('shows the platform icon matching the media format', () => {
        const saoleiWork = { ...mediaItem, id: 9, format: 'c_p', title: 'Saolei post', suffix: '9786' };
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, {
            body: { ...pageBody, items: [mediaItem, saoleiWork] },
        });
        mountPanel();
        cy.get('[data-cy=media-row-7] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://www.bilibili.com/favicon.ico');
        cy.get('[data-cy=media-row-9] [data-cy=media-platform-icon]').should('have.attr', 'src', 'https://saolei.wang/icon.svg').
            and('have.attr', 'alt', 'Saolei.wang');
    });

    it('renders the GitHub icon as a theme-following mask', () => {
        const githubWork = { ...mediaItem, id: 10, format: 'g_r', title: 'GitHub repo', suffix: 'owner/repo' };
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, {
            body: { ...pageBody, items: [githubWork] },
        });
        mountPanel();
        cy.get('[data-cy=media-row-10] [data-cy=media-platform-icon]').
            should('have.class', 'media-platform-mask').
            and('have.attr', 'aria-label', 'GitHub').
            and('have.attr', 'style').
            and('contain', 'github.svg');
    });

    it('shows the repository owner/name and description for GitHub works', () => {
        const githubWork = { ...mediaItem, id: 12, format: 'g_r', title: 'owner/project', suffix: '42' };
        cy.intercept('GET', 'https://api.github.com/repositories/42', {
            body: { id: 42, full_name: 'owner/project', description: 'Minesweeper client', html_url: 'https://github.com/owner/project' },
        }).as('repository');
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, {
            body: { ...pageBody, items: [githubWork] },
        });
        mountPanel();
        cy.wait('@repository');
        cy.get('[data-cy=media-row-12] [data-cy=media-title-link]').
            should('have.attr', 'href', 'https://github.com/owner/project').
            and('have.text', 'owner/project: Minesweeper client').
            and('have.attr', 'title', 'owner/project: Minesweeper client');
    });

    it('switches the backend sort through the table headers', () => {
        mountPanel();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'submitted');
        cy.get('[data-sort=submitted]').should('have.attr', 'aria-pressed', 'true');
        cy.get('.base-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.[2]).to.equal(new Date(mediaItem.submitted_at).toLocaleString('en'));
        });
        cy.get('[data-cy=works-time-sort-toggle]').should('have.attr', 'aria-label', 'Sort by publication time').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'latest');
        cy.get('[data-sort=latest]').should('have.attr', 'aria-pressed', 'true');
        cy.get('.base-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.[2]).to.equal(new Date(mediaItem.created_at).toLocaleString('en'));
        });
        cy.get('[data-sort=likes]').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'likes');
        cy.get('[data-sort=latest]').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'latest');
        cy.get('[data-sort=hot]').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'hot');
        cy.get('[data-cy=works-time-sort-toggle]').should('have.attr', 'aria-label', 'Sort by submission time').click();
        cy.wait('@ranking').its('request.query.sort').should('eq', 'submitted');
        cy.get('[data-sort=submitted]').should('have.attr', 'aria-pressed', 'true');
    });

    it('opens a preview dialog for embeddable works instead of following the external link', () => {
        const embeddable = {
            ...mediaItem,
            id: 8,
            title: 'Embeddable work',
            format: 'B_v',
            suffix: 'BV1xx411c7mD',
        };
        cy.intercept({ method: 'GET', pathname: '/api/media/works' }, {
            body: { ...pageBody, items: [mediaItem, embeddable] },
        });
        mountPanel();
        cy.get('[data-cy=media-row-7] [data-cy=media-title-link]').should('have.attr', 'href', 'https://www.bilibili.com/read/cv1646742');
        cy.get('[data-cy=media-row-8] [data-cy=media-title-link]').should('not.exist');
        cy.get('[data-cy=media-row-8] [data-cy=media-preview-link]').should('contain.text', 'Embeddable work').click();
        cy.get('.el-dialog:visible iframe.media-preview-frame').should('have.attr', 'src', 'https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&page=1&autoplay=0&danmaku=0');
        cy.get('.el-dialog:visible a.media-preview-external').should('have.attr', 'href', 'https://www.bilibili.com/video/BV1xx411c7mD/');
    });

    it('reloads /me after an in-page login', () => {
        let calls = 0;
        cy.intercept({ method: 'GET', pathname: '/api/media/me' }, (request) => {
            calls += 1;
            request.reply({ body: { balance: calls === 1 ? 5 : 42, likes_sent: 0, banned: false, daily_likes_used: 3 } });
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
