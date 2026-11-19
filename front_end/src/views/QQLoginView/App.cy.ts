import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import QQLoginWelcome from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';

const pendingStatus = {
    user_id: 0,
    username: '',
    configured: true,
    login_enabled: true,
    linked: false,
    profile: null,
    pending: { nickname: 'QQ Player', avatar_url: '' },
    can_unlink: false,
    has_email: false,
    can_set_username: false,
};

describe('QQ login welcome', () => {
    beforeEach(() => {
        store.logout();
    });

    function mountWelcome() {
        const empty = defineComponent({ expose: [], render: () => h('div') });
        const router = createRouter({ history: createMemoryHistory(),
            routes: [
                { path: '/qq-login', name: 'qq-login', component: empty },
                { path: '/login', component: empty },
            ] });
        cy.wrap(router.push('/qq-login?result=pending'));
        cy.mount(QQLoginWelcome, { global: { plugins: [i18n, router], config: { globalProperties: { $axios } } } });
        return router;
    }

    it('does not register automatically and discards authorization for an existing account', () => {
        cy.intercept('GET', '/api/userprofile/qq/status', { body: pendingStatus });
        cy.intercept('POST', '/api/userprofile/qq/register', { body: {} }).as('register');
        cy.intercept('POST', '/api/userprofile/qq/cancel', { body: {} }).as('cancel');
        const router = mountWelcome();
        cy.contains('QQ Player').should('be.visible');
        cy.contains('creates a second account').should('be.visible');
        cy.get('@register.all').should('have.length', 0);
        cy.contains('button', 'I already have an account').click();
        cy.wait('@cancel');
        cy.then(() => {
            expect(router.currentRoute.value.path).to.equal('/login');
        });
        cy.get('@register.all').should('have.length', 0);
    });

    it('creates an account only on explicit confirmation and shows the new-account notice', () => {
        let registered = false;
        cy.intercept('GET', '/api/userprofile/qq/status', (request) => {
            request.reply({ body: registered
                ? {
                    ...pendingStatus,
                    user_id: 7,
                    username: 'qq_test',
                    linked: true,
                    pending: null,
                    profile: pendingStatus.pending,
                }
                : pendingStatus });
        });
        cy.intercept('POST', '/api/userprofile/qq/register', (request) => {
            registered = true;
            request.reply({ body: { user: { id: 7, username: 'qq_test' } } });
        }).as('register');
        mountWelcome();
        cy.contains('button', 'Create an account with QQ anyway').click();
        cy.wait('@register');
        cy.get('[data-cy=qq-new-account]').should('contain', 'This is a new account');
        cy.contains('a', 'Manage QQ login').should('have.attr', 'href').and('contain', '/player/7/accountlink?qq_login=manage');
    });
});
