import { h } from 'vue';
import { RouterView } from 'vue-router';

import DatabaseApp from './App.vue';
import UserView from './UserView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { DirectoryUser, UserDirectorySort } from '@/services/userDirectoryService';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const users: DirectoryUser[] = [
    {
        id: 42,
        date_joined: new Date(2024, 0, 2, 3, 4, 5).toISOString(),
        accounts: { c: '101', a: '201', w: '301', m: 'mr-alpha_01' },
        statistics: { video_num_total: 2, video_num_tournament: 3, video_num_all: 5, video_size_total: 1024, video_size_tournament: 2048, video_size_all: 3072 },
    },
    {
        id: 43,
        date_joined: new Date(2025, 5, 7, 8, 9, 10).toISOString(),
        accounts: { m: 'mr-linked_03' },
        statistics: { video_num_total: -1, video_num_tournament: 0, video_num_all: -1, video_size_total: -1024, video_size_tournament: 0, video_size_all: -1024 },
    },
];

function mountDirectory() {
    const emptyView = { render: () => h('div') };
    const router = hashRouter({
        initialPath: '/database',
        routes: [
            {
                path: '/database',
                component: DatabaseApp,
                redirect: { name: 'database-users' },
                children: [
                    { path: 'users', name: 'database-users', component: UserView },
                    { path: 'videos', name: 'database-videos', component: emptyView },
                    { path: 'identifiers', name: 'database-identifiers', component: emptyView },
                ],
            },
            { path: '/player/:id', name: 'player_id', component: emptyView },
        ],
    });
    cy.mount({ render: () => h(RouterView) }, {
        global: { plugins: [i18n, pinia, router], stubs: { transition: false }, config: { globalProperties: { $axios } } },
    });
    return router;
}

describe('Database users', () => {
    installHashHistoryCleanup();

    it('opens the first Users tab and displays dates, platform IDs and statistics', () => {
        cy.intercept('GET', '**/api/userprofile/query*', { count: 41, users }).as('users');
        const router = mountDirectory();
        cy.wait('@users').its('request.query').should('include', { sort: 'id', reverse: 'false', page: '1', page_size: '20' });
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/database/users');
        cy.get('[role=tab]').first().should('have.text', 'Users').and('have.attr', 'aria-selected', 'true');
        cy.get('.user-directory-table thead tr').first().find('th').eq(1).should('contain.text', 'Date joined');
        cy.get('.user-directory-table tbody').extractTableData().should('deep.equal', [
            ['42', '2024-01-02 03:04:05', '101', '201', '301', 'mr-alpha_01', '2', '3', '5', '1.00 KB', '2.00 KB', '3.00 KB'],
            ['43', '2025-06-07 08:09:10', '', '', '', 'mr-linked_03', '-1', '0', '-1', '-1.00 KB', '0 B', '-1.00 KB'],
        ]);
        cy.get('.user-directory-table tbody time').first().should('have.attr', 'datetime', users[0].date_joined);
        cy.get('.user-directory-table tbody a').first().should('have.attr', 'href', '#/player/42');
        cy.get('[data-field=video_size_all]').first().should('have.attr', 'title', '3,072 B');
        const profiles = [
            ['c', 'http://saolei.wang/Player/Index.asp?Id=101'], ['a', 'https://minesweepergame.com/profile.php?pid=201'],
            ['w', 'https://minesweeper.online/player/301'],
        ];
        for (const [platform, href] of profiles) {
            cy.get(`[data-platform=${platform}] a`).first().should('have.attr', 'href', href).and('have.attr', 'target', '_blank');
        }
        cy.get('[data-platform=m]').first().should('contain.text', 'mr-alpha_01').find('a').should('not.exist');
        cy.contains('[role=tab]', 'Videos').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/database/videos');
        cy.contains('[role=tab]', 'Users').click();
        cy.get('.user-directory-table tbody tr').should('have.length', 2);
    });

    it('toggles ID and statistic sorting and resets pagination', () => {
        cy.intercept('GET', '**/api/userprofile/query*', { count: 41, users }).as('users');
        mountDirectory();
        cy.wait('@users');
        cy.get('.user-directory-pagination .btn-next').click();
        cy.wait('@users').its('request.query').should('include', { page: '2' });
        const fields: UserDirectorySort[] = ['id', 'video_size_all'];
        for (const field of fields) {
            cy.get(`[data-sort=${field}]`).click();
            cy.wait('@users').its('request.query').should('include', { sort: field, reverse: 'true', page: '1' });
            cy.get(`[data-sort=${field}]`).closest('th').should('have.attr', 'aria-sort', 'descending');
            cy.get(`[data-sort=${field}]`).click();
            cy.wait('@users').its('request.query').should('include', { sort: field, reverse: 'false', page: '1' });
            cy.get(`[data-sort=${field}]`).closest('th').should('have.attr', 'aria-sort', 'ascending');
        }
    });

    it('queries one platform and ID at a time and clears the filter while preserving the selected sort', () => {
        cy.intercept('GET', '**/api/userprofile/query*', { count: 41, users }).as('users');
        mountDirectory();
        cy.wait('@users');
        cy.get('.user-directory-filters input').should('have.length', 1);
        cy.get('[data-sort=video_num_all]').click();
        cy.wait('@users');
        cy.get('.user-directory-pagination .btn-next').click();
        cy.wait('@users');
        const searches = [['', '42'], ['m', 'mr-alpha_01']];
        for (const [platform, id] of searches) {
            cy.get('#user-query-platform').select(platform);
            cy.get('#user-query-id').clear();
            cy.get('#user-query-id').type(`${id}{enter}`);
            cy.wait('@users').its('request.query').should('include', { platform, id, page: '1', sort: 'video_num_all' });
        }
        cy.get('[data-cy=user-query-reset]').click();
        cy.wait('@users').its('request.query').should('include', { platform: '', id: '', sort: 'video_num_all' });
        cy.get('#user-query-platform').should('have.value', '');
        cy.get('#user-query-id').should('have.value', '');
    });

    it('shows empty results and supports retry after a failed request', () => {
        cy.intercept('GET', '**/api/userprofile/query*', { statusCode: 500 }).as('failed');
        mountDirectory();
        cy.wait('@failed');
        cy.get('.user-directory [role=alert]').should('contain.text', 'Unable to load users');
        cy.closeElNotifications();
        cy.intercept('GET', '**/api/userprofile/query*', { count: 0, users: [] }).as('empty');
        cy.contains('button', 'Retry').click();
        cy.wait('@empty');
        cy.get('.user-directory-table').should('contain.text', 'No matching users');
        cy.get('.user-directory [role=alert]').should('not.exist');
    });
});
