import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import Login from './App.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { local, store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

const Blank = defineComponent({
    setup() {
        return () => h('div');
    },
});

function testRouter(initial: string) {
    const router = createRouter({
        history: createMemoryHistory(),
        routes: [
            { path: '/', alias: ['/login', '/register'], component: Blank },
            { path: '/elsewhere', component: Blank },
        ],
    });
    void router.replace(initial);
    return router;
}

function mountLogin(initial: string, user: UserProfileData | null) {
    const router = testRouter(initial);
    cy.intercept('GET', '/api/common/loginauto*', { user, top_anchors: {} }).as('restore');
    cy.wrap(router.isReady()).then(() => {
        cy.mount(Login, {
            global: { plugins: [i18n, router], config: { globalProperties: { $axios } } },
            slots: { default: () => h('output', { 'data-cy': 'login-user' }, String(store.user.id)) },
        });
    });
    cy.wait('@restore');
    return router;
}

function restore(user: UserProfileData) {
    mountLogin('/', user);
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

describe('login and register page routes', () => {
    beforeEach(() => {
        local.value.language = 'en';
        store.logout();
        cy.clearCookie('csrftoken');
    });
    afterEach(() => {
        cy.get('@vue').invoke('unmount');
        cy.closeElNotifications();
        store.logout();
    });

    it('opens the login dialog at /login', () => {
        const router = mountLogin('/login', null);
        cy.get('.el-dialog').should('be.visible');
        cy.get('.el-dialog__title').should('have.text', 'Login');
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/login');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('opens the register dialog at /register', () => {
        const router = mountLogin('/register', null);
        cy.get('.el-dialog').should('be.visible');
        cy.get('.el-dialog__title').should('have.text', 'Register');
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/register');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('returns to the home route when the page dialog is closed', () => {
        const router = mountLogin('/login', null);
        cy.get('.el-dialog').should('be.visible');
        cy.get('.el-dialog__headerbtn').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/');
        cy.shouldBeAbsentOrHidden('.el-dialog');
    });

    it('closes a route-opened dialog when navigating away from the login route', () => {
        const router = mountLogin('/login', null);
        cy.get('.el-dialog').should('be.visible');
        cy.then(() => router.push('/elsewhere'));
        cy.shouldBeAbsentOrHidden('.el-dialog');
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/elsewhere');
    });

    it('redirects a logged-in visitor back home without showing the dialog', () => {
        const router = mountLogin('/login', { id: 7, username: 'ordinary' });
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/');
        cy.shouldBeAbsentOrHidden('.el-dialog');
    });
});
