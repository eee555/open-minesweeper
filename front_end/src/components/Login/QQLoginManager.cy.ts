import QQLoginManager from './QQLoginManager.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const status = {
    user_id: 7,
    username: 'qq_test',
    configured: true,
    login_enabled: true,
    linked: true,
    profile: { nickname: 'QQ Player', avatar_url: '' },
    pending: null,
    can_unlink: false,
    has_email: false,
    can_set_username: false,
};
const options = { global: {
    plugins: [i18n],
    config: { globalProperties: { $axios } },
    stubs: { RouterLink: true, EmailFormItem: true, EmailCodeBlock: true },
} };

describe('QQ login management', () => {
    it('shows only private QQ profile details and prevents removal of the only login', () => {
        cy.intercept('GET', '/api/userprofile/qq/status', { body: status });
        cy.mount(QQLoginManager, options);
        cy.contains('QQ Player').should('be.visible');
        cy.contains('button', 'Unbind QQ login').should('be.disabled');
        cy.contains('QQ is your only login method').should('be.visible');
    });

    it('confirms unbinding and reloads the binding state', () => {
        let linked = true;
        cy.intercept('GET', '/api/userprofile/qq/status', (request) => {
            request.reply({ body: { ...status, linked, can_unlink: true, has_email: true, profile: linked ? status.profile : null } });
        });
        cy.intercept('POST', '/api/userprofile/qq/unlink', (request) => {
            linked = false;
            request.reply({ body: {} });
        }).as('unlink');
        cy.on('window:confirm', () => true);
        cy.mount(QQLoginManager, options);
        cy.contains('button', 'Unbind QQ login').click();
        cy.wait('@unlink');
        cy.contains('QQ login is not bound').should('be.visible');
        cy.contains('button', 'Bind QQ login').should('be.visible');
    });
});
