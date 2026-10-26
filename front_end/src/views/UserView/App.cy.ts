import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';

import App from './App.vue';
import { userRoutes } from './routes';
import UserPBView from './UserPBView.vue';
import UserSettingsView from './UserSettingsView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { invalidateProfileData } from '@/services/profileDataService';
import { store } from '@/store';
import { pinia } from '@/store/create';

const TopStub = defineComponent(() => () => h('div', { 'data-cy': 'top-content' }, 'top content'));
const RouterRoot = defineComponent({ expose: [], render: () => h(RouterView) });

function mountProfile(path: string, loggedIn = true) {
    cy.intercept('GET', '/api/userprofile/info/43*', { id: 43, username: 'other', realname: 'Other' });
    cy.intercept('GET', '/api/userprofile/identifier*', ['Owned identifier']).as('identifiers');
    cy.intercept('GET', '/api/userprofile/videolist*', []).as('videos');
    cy.intercept('GET', '/api/speedranking/player/42', { saolei: { et: 35090 } }).as('qualification');
    const router = createRouter({
        history: createMemoryHistory(),
        routes: [{
            path: '/player/:id',
            component: App,
            redirect: (to) => ({ name: 'user-top', params: to.params }),
            children: userRoutes.map((route) => {
                if (route.name === 'user-top') return { path: route.path, name: route.name, component: TopStub };
                if (route.name === 'user-pb') return { path: route.path, name: route.name, component: UserPBView };
                if (route.name === 'user-settings') return { path: route.path, name: route.name, component: UserSettingsView };
                return route;
            }),
        }],
    });
    cy.then(() => {
        // A previous mount may have cached the qualification response for this player.
        invalidateProfileData(42);
        if (loggedIn) store.login({ id: 42, username: 'self', realname: 'Self' });
        else store.logout();
        return router.push(path);
    });
    cy.then(() => router.isReady()).then(() => {
        cy.mount(RouterRoot, {
            global: {
                plugins: [i18n, pinia, router],
                stubs: { Avatar: true },
                config: { globalProperties: { $axios } },
            },
        });
    });
    return router;
}

describe('Profile tab navigation', () => {
    it('defaults to the top-level top tab and loads PB only when selected', () => {
        cy.intercept('GET', '/api/speedranking/pb/player/42', []).as('pb');
        const router = mountProfile('/player/42');
        cy.wrap(router).its('currentRoute.value.name').should('eq', 'user-top');
        cy.get('[data-cy=profile-tabs] > .el-tabs__header [role=tab]').should(($tabs) => {
            expect($tabs.toArray().map((tab) => tab.textContent?.trim())).to.deep.equal(['Top', 'PB', 'Record', 'Account Link', 'Videos', 'Medals', 'Upload', 'Settings']);
        });
        cy.get('[data-cy=top-content]').should('be.visible');
        cy.get('@pb.all').should('have.length', 0);
        cy.get('[data-cy=profile-tabs] > .el-tabs__header [role=tab]').contains('PB').click();
        cy.wrap(router).its('currentRoute.value.name').should('eq', 'user-pb');
        cy.wait('@pb');
        cy.get('[data-cy=pb-grid-e]').should('be.visible');
        cy.get('[data-cy=profile-tabs] > .el-tabs__header [role=tab]').contains(/^Top$/).click();
        cy.get('[data-cy=top-content]').should('be.visible');
        cy.get('[data-cy=profile-tabs] > .el-tabs__header [role=tab]').contains('PB').click();
        cy.get('[data-cy=pb-grid-e]').should('be.visible');
        cy.get('@pb.all').should('have.length', 1);
        cy.get('@videos.all').should('have.length', 0);
    });

    it('opens the settings route from Edit Profile and renders the form and identifiers inline', () => {
        const router = mountProfile('/player/42/top');
        cy.contains('button', 'Edit Profile').click();
        cy.wrap(router).its('currentRoute.value.name').should('eq', 'user-settings');
        cy.wait('@qualification');
        cy.wait('@identifiers');
        cy.get('.user-settings').should('contain.text', 'Local Name').and('contain.text', 'Owned identifier');
        cy.get('.user-settings').contains('Local Name').parent().next().find('input').should('have.value', 'Self');
        cy.get('.el-dialog').should('not.exist');
        cy.get('@videos.all').should('have.length', 0);
    });

    for (const loggedIn of [true, false]) {
        it(`redirects ${loggedIn ? 'another player' : 'a guest'} away from settings`, () => {
            const router = mountProfile('/player/43/settings', loggedIn);
            cy.wrap(router).its('currentRoute.value.name').should('eq', 'user-top');
            cy.get('.user-settings').should('not.exist');
            cy.contains('.el-tabs__item', 'Settings').should('not.exist');
            cy.contains('button', 'Edit Profile').should('not.exist');
        });
    }
});
