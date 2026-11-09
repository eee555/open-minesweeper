import MediaCard from './MediaCard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { MediaItem } from '@/services/mediaService';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const baseMedia: MediaItem = {
    id: 7,
    title: 'Test work',
    language: 'zh-cn',
    created_at: '2026-01-01T00:00:00Z',
    submitted_at: '2026-01-02T00:00:00Z',
    format: 'B_v',
    status: 'verified',
    rejected_at: null,
    reject_reason: '',
    refunded_likes: 0,
    likes: 12,
    hot_value: 10,
    hot_value_updated_at: '2026-01-01T00:00:00Z',
    metadata_pending: false,
    user_id: 42,
    rejected_by: null,
    url: 'https://example.com/work/7',
    embed_url: null,
    hot_now: 9.87,
};

describe('<MediaCard />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        cy.mockPlayerNameFallback();
    });

    function mountCard(overrides: Partial<MediaItem> = {}, extraProps: Record<string, unknown> = {}) {
        cy.mount(MediaCard, {
            props: { media: { ...baseMedia, ...overrides }, ...extraProps },
            global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } },
        });
    }

    it('renders title, author link, language, status and stats', () => {
        mountCard({}, { showStatus: true });
        cy.get('[data-cy=media-card-7] .media-card-title').should('have.text', 'Test work').
            and('have.attr', 'href', 'https://example.com/work/7');
        cy.get('[data-cy=media-card-7]').should('contain.text', '简体中文').
            and('contain.text', '12').and('contain.text', '9.87');
        cy.get('[data-cy=media-card-7] .media-card-status--verified').should('have.text', 'Verified');
        cy.get('[data-cy=media-card-7] a[href="#/player/42"]').should('exist');
    });

    it('shows a placeholder title and pending badge for degraded submissions', () => {
        mountCard({ title: '', metadata_pending: true, status: 'pending', language: '' }, { showStatus: true });
        cy.get('[data-cy=media-card-7]').should('contain.text', 'Title to be filled').
            and('contain.text', 'Unknown language');
        cy.get('[data-cy=media-card-7] .media-card-status--pending').should('have.length', 2);
    });

    it('shows reject reason and rejecting moderator when requested', () => {
        mountCard({ status: 'rejected', reject_reason: 'Not minesweeper related', rejected_by: 99 }, { showRejectInfo: true });
        cy.get('[data-cy=media-card-7] .media-card-reject').should('contain.text', 'Not minesweeper related');
        cy.get('[data-cy=media-card-7] a[href="#/player/99"]').should('exist');
    });

    it('keeps the feed button disabled when the viewer cannot feed', () => {
        mountCard({}, { feedDisabled: true });
        cy.get('[data-cy=media-card-7] .media-card-stats button').should('be.disabled');
    });
});
