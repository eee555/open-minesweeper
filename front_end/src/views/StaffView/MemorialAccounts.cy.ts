import { createMemoryHistory, createRouter } from 'vue-router';

import MemorialAccounts from './MemorialAccounts.vue';

import $axios from '@/http';

const target = { id: 42, userms_id: 70, username: 'legend', realname: '传奇玩家', firstname: '', lastname: '', is_memorial: true };

function mountPage() {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: MemorialAccounts }] });
    cy.wrap(router.push('/?id=42')).then(() => {
        cy.mount(MemorialAccounts, { global: { plugins: [router], config: { globalProperties: { $axios } } } });
    });
}

describe('<MemorialAccounts />', () => {
    it('does not expose upload controls when the server rejects access', () => {
        cy.intercept('GET', '**/api/common/admin/memorial/users/42/videos', { statusCode: 401, body: { detail: 'Unauthorized' } });
        mountPage();
        cy.get('[role=alert]').should('exist');
        cy.get('[data-cy=memorial-upload-controls]').should('not.exist');
    });

    it('requires manual selection and displays a successful upload despite binding failure', () => {
        cy.intercept('GET', '**/api/common/admin/memorial/users/42/videos', { body: { user: target, csrf_token: 'csrf' } }).as('access');
        cy.intercept('POST', '**/api/common/admin/memorial/users/42/videos', { body: {
            video: { id: 91, state: 'b', upload_time: '2008-08-08T12:00:00Z' },
            bindings: [{ identifier: 'selected', bound: false, error: '绑定失败' }],
        } }).as('upload');
        mountPage();
        cy.wait('@access');
        cy.get('[data-cy=memorial-files]').selectFile('cypress/fixtures/standard_gsc.evf');
        cy.get('[data-cy=memorial-identifier]').should('have.length', 1).and('not.be.checked');
        cy.get('[data-cy=memorial-upload-submit]').should('be.disabled');
        cy.get('[data-cy=memorial-upload-anchor] input').clear();
        cy.get('[data-cy=memorial-upload-anchor] input').type('2008-08-08 12:00:00{enter}');
        cy.get('[data-cy=memorial-identifier]').check();
        cy.get('[data-cy=memorial-upload-submit]').click();
        cy.wait('@upload');
        cy.get('[data-cy=memorial-bindings]').should('contain.text', '绑定失败');
        cy.get('[data-cy=memorial-upload-results]').should('contain.text', '录像 #91');
    });
});
