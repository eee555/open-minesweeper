import { h } from 'vue';

import Login from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

function restore(user: UserProfileData) {
    cy.intercept('GET', '/api/common/loginauto*', { user, top_anchors: {} }).as('restore');
    cy.mount(Login, {
        global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        slots: { default: () => h('output', { 'data-cy': 'login-user' }, String(store.user.id)) },
    });
    cy.wait('@restore');
    cy.get('[data-cy=login-user]').should('have.text', String(user.id));
}

describe('login session CSRF loading', () => {
    beforeEach(() => {
        store.logout();
        cy.clearCookie('csrftoken');
    });
    afterEach(() => {
        store.logout();
    });

    it('keeps ordinary user requests free of CSRF bootstrap and headers', () => {
        let bootstraps = 0;
        cy.intercept('GET', '/api/userprofile/admin/csrf', (request) => {
            bootstraps++;
            request.reply({ csrf_token: 'unexpected-token' });
        });
        cy.intercept('POST', '/ordinary-action', (request) => {
            expect(request.headers).not.to.have.property('x-csrftoken');
            request.reply({ ok: true });
        }).as('write');
        restore({ id: 7, username: 'ordinary' });
        cy.then(() => $axios.post('/ordinary-action'));
        cy.wait('@write');
        cy.then(() => expect(bootstraps).to.equal(0));
    });

    for (const [name, role] of [['staff', { is_staff: true }], ['superuser', { is_superuser: true }]] as const) {
        it(`prepares the first management write after restoring ${name}`, () => {
            cy.intercept('GET', '/api/userprofile/admin/csrf', { csrf_token: 'lazy-token' }).as('csrf');
            cy.intercept('POST', '/api/common/tasks/cleanup', (request) => {
                expect(request.headers['x-csrftoken']).to.equal('lazy-token');
                request.reply({ statusCode: 200, body: 0 });
            }).as('write');
            restore({ id: 42, username: 'manager', ...role });
            cy.then(() => $axios.post('/api/common/tasks/cleanup'));
            cy.wait('@csrf');
            cy.wait('@write');
        });
    }
});
