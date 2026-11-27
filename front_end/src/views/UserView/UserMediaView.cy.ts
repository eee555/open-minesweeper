import { createMemoryHistory, createRouter } from 'vue-router';

import UserMediaView from './UserMediaView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { resetGitHubRepositoryCache } from '@/services/githubService';

const mediaItem = {
    id: 7,
    title: 'owner/project',
    language: 'en',
    created_at: '2026-01-01T00:00:00Z',
    submitted_at: '2026-01-01T00:00:00Z',
    format: 'g_r',
    status: 'verified',
    rejected_at: null,
    reject_reason: '',
    refunded_likes: 0,
    likes: 3,
    hot_value: 3.1,
    hot_value_updated_at: '2026-01-01T00:00:00Z',
    metadata_pending: false,
    user_id: 99,
    rejected_by: null,
    suffix: '42',
    hot_now: 3,
};

describe('<UserMediaView />', () => {
    beforeEach(() => {
        resetGitHubRepositoryCache();
    });

    it('shows the repository owner/name and description on the works tab', () => {
        cy.intercept({ method: 'GET', pathname: '/api/media/user/99' }, {
            // eslint-disable-next-line @typescript-eslint/no-deprecated -- Cypress body 上下文含 string，anchor 键误命中 String.prototype.anchor
            body: { items: [mediaItem], total: 1, start: 0, anchor: new Date().toISOString() },
        }).as('userMedia');
        cy.intercept('GET', 'https://api.github.com/repositories/42', {
            body: { id: 42, full_name: 'owner/project', description: 'Minesweeper client', html_url: 'https://github.com/owner/project' },
        }).as('repository');
        const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/player/:id/works', name: 'user-works', component: UserMediaView }] });
        void router.push('/player/99/works');
        cy.wrap(router.isReady()).then(() => {
            cy.mount(UserMediaView, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@userMedia');
        cy.wait('@repository');
        cy.get('.base-table tbody tr a').should('have.attr', 'href', 'https://github.com/owner/project').
            and('have.text', 'owner/project: Minesweeper client').
            and('have.attr', 'title', 'owner/project: Minesweeper client');
    });
});
