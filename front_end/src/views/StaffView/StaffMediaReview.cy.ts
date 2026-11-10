import StaffMediaReview from './StaffMediaReview.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const anchor = new Date().toISOString();
const verifiedWork = {
    id: 7,
    title: 'Verified work',
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
    hot_value_updated_at: anchor,
    metadata_pending: false,
    user_id: 42,
    rejected_by: null,
    url: 'https://www.bilibili.com/video/BV1xx411c7mD/',
    embed_url: null,
    hot_now: 3,
};

describe('<StaffMediaReview />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        store.user.is_staff = true;
        store.user.is_superuser = true;
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/media/pending' }, {
            body: { items: [], total: 0, start: 0, anchor },
        }).as('pending');
        cy.intercept({ method: 'GET', pathname: '/api/media/latest' }, {
            body: { items: [verifiedWork], total: 1, start: 0, anchor },
        }).as('latest');
    });

    it('lists verified works so a superuser can select one for hard deletion', () => {
        const router = hashRouter({ initialPath: '/staff/media' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(StaffMediaReview, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@pending');
        cy.contains('button', 'Verified').click();
        cy.wait('@latest');
        cy.get('table tbody').extractTableData().should((data) => {
            expect(data[0]?.[0]).to.equal('7');
            expect(data[0]?.[3]).to.equal('verified');
        });
        cy.contains('button', 'Select').click();
        cy.contains('button', 'Hard delete').should('exist');
    });

    it('keeps the verified work selected after approving a pending one', () => {
        const pendingWork = { ...verifiedWork, id: 8, status: 'pending', title: 'Pending work' };
        cy.intercept({ method: 'GET', pathname: '/api/media/pending' }, {
            body: { items: [pendingWork], total: 1, start: 0, anchor },
        }).as('pending');
        cy.intercept('POST', '/api/media/admin/verify', { body: verifiedWork }).as('verify');
        const router = hashRouter({ initialPath: '/staff/media' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(StaffMediaReview, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@pending');
        cy.contains('button', 'Select').click();
        cy.get('[data-cy=review-external-author-id]').should('not.exist');
        cy.get('[data-cy=review-id-hint]').should('not.exist');
        cy.get('[data-cy=review-title]').should('not.exist');
        cy.get('[data-cy=review-identity-confirmed]').should('exist');
        cy.contains('button', /^\s*Verify\s*$/).click();
        cy.wait('@verify').its('request.body').should('deep.equal', { id: 8 });
        cy.wait('@latest');
        cy.contains('.media-review-form', '#7').should('exist');
        cy.contains('button', 'Hard delete').should('exist');
    });

    it('still requires the external author id for a degraded submission', () => {
        const degradedWork = { ...verifiedWork, id: 9, status: 'pending', title: '', metadata_pending: true };
        cy.intercept({ method: 'GET', pathname: '/api/media/pending' }, {
            body: { items: [degradedWork], total: 1, start: 0, anchor },
        }).as('pending');
        cy.intercept('POST', '/api/media/admin/verify', { body: { ...degradedWork, status: 'verified' } }).as('verify');
        const router = hashRouter({ initialPath: '/staff/media' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(StaffMediaReview, {
                global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            });
        });
        cy.wait('@pending');
        cy.contains('button', 'Select').click();
        cy.get('[data-cy=review-external-author-id]').should('exist');
        cy.get('[data-cy=review-id-hint]').should('exist');
        cy.get('[data-cy=review-identity-confirmed]').should('not.exist');
        cy.contains('button', /^\s*Verify\s*$/).click();
        cy.get('.el-notification').should('contain.text', 'requires both a title and an external author id');
        cy.closeElNotifications();
        cy.get('[data-cy=review-title]').type('Manual title');
        cy.get('[data-cy=review-external-author-id]').type('42');
        cy.contains('button', /^\s*Verify\s*$/).click();
        cy.wait('@verify').its('request.body').should('deep.equal', { id: 9, title: 'Manual title', external_author_id: '42' });
        cy.closeElNotifications();
    });
});
