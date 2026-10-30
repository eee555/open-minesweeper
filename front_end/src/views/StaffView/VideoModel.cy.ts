import VideoModel from './VideoModel.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { installAdminCsrfInterceptor } from '@/services/adminCsrf';

let csrfInterceptor: number | undefined;

afterEach(() => {
    if (csrfInterceptor !== undefined) $axios.interceptors.request.eject(csrfInterceptor);
    csrfInterceptor = undefined;
});

function loadVideo(reason = '') {
    cy.intercept('GET', '/api/video/admin/detail/12', { id: 12, state: reason ? 'b' : 'c', video__freeze_reason: reason }).as('detail');
    cy.mount(VideoModel, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    cy.get('[data-cy=video-id] input').clear();
    cy.get('[data-cy=video-id] input').type('12');
    cy.get('[data-cy=video-query]').click();
    cy.wait('@detail');
}

describe('staff video freezing', () => {
    it('automatically supplies CSRF for an existing staff action through the website interceptor', () => {
        cy.clearCookie('csrftoken');
        csrfInterceptor = installAdminCsrfInterceptor($axios, () => true);
        cy.intercept('GET', '/api/userprofile/admin/csrf', { csrf_token: 'staff-token' }).as('csrf');
        cy.intercept('POST', '/api/video/newest_queue/remove', (request) => {
            expect(request.headers['x-csrftoken']).to.equal('staff-token');
            request.reply({ statusCode: 204, body: '' });
        }).as('removeNewest');
        loadVideo();
        cy.contains('button', 'Remove from latest videos').click();
        cy.wait('@csrf');
        cy.wait('@removeNewest');
        cy.closeElNotifications();
    });

    it('requires a loaded video and a reason, then saves the trimmed multiline reason with CSRF', () => {
        const reason = 'First line\nSecond line';
        cy.intercept('GET', '/api/video/admin/freeze', { csrf_token: 'freeze-token' }).as('access');
        cy.intercept('POST', '/api/video/admin/freeze', (request) => {
            expect(request.headers['x-csrftoken']).to.equal('freeze-token');
            expect(request.headers['content-type']).to.contain('application/json');
            expect(request.body).to.deep.equal({ id: 12, freeze_reason: reason });
            request.reply({ id: 12, state: 'b', freeze_reason: reason });
        }).as('freeze');
        loadVideo();
        cy.get('[data-cy=freeze-video]').should('be.disabled');
        cy.get('[data-cy=freeze-reason]').type(`  ${reason}  `);
        cy.get('[data-cy=freeze-video]').click();
        cy.wait('@access');
        cy.wait('@freeze');
        cy.closeElNotifications();
        cy.get('[data-cy=video-detail]').should('contain.text', reason);
        cy.get('[data-cy=freeze-reason]').should('have.value', reason);
        cy.get('[data-cy=video-id] input').clear();
        cy.get('[data-cy=video-id] input').type('13');
        cy.get('[data-cy=freeze-video]').should('be.disabled');
    });

    it('loads and lets staff edit the saved reason', () => {
        loadVideo('Original reason');
        cy.get('[data-cy=freeze-reason]').should('have.value', 'Original reason');
        cy.get('[data-cy=freeze-reason]').clear();
        cy.get('[data-cy=freeze-reason]').type('Updated reason');
        cy.get('[data-cy=freeze-video]').should('not.be.disabled');
    });

    it('keeps the draft and current details when freezing fails', () => {
        cy.intercept('GET', '/api/video/admin/freeze', { csrf_token: 'freeze-token' });
        cy.intercept('POST', '/api/video/admin/freeze', { statusCode: 403, body: { detail: 'Forbidden' } }).as('freeze');
        loadVideo();
        cy.get('[data-cy=freeze-reason]').type('Draft reason');
        cy.get('[data-cy=freeze-video]').click();
        cy.wait('@freeze');
        cy.closeElNotifications();
        cy.get('[data-cy=freeze-reason]').should('have.value', 'Draft reason');
        cy.get('[data-cy=video-detail]').should('not.contain.text', 'Draft reason');
        cy.get('[data-cy=freeze-video]').should('not.be.disabled');
    });
});
