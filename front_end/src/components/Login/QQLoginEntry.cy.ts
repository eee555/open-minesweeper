import { ElMessage } from 'element-plus';
import { createI18n } from 'vue-i18n';

import QQLoginEntry from './QQLoginEntry.vue';

import i18n from '@/i18n';

describe('<QQLoginEntry />', () => {
    const mountOptions = { global: { plugins: [i18n] } };
    afterEach(() => {
        ElMessage.closeAll();
    });

    it('renders the official 16×16 badge with fixed Chinese text', () => {
        cy.mount(QQLoginEntry, mountOptions);
        cy.get('.qq-login-entry img').should('have.attr', 'src', `${import.meta.env.BASE_URL}img/qq_login_16x16.png`).and('have.attr', 'width', '16').and('have.attr', 'height', '16').and('have.attr', 'alt', '');
        cy.get('.qq-login-entry img').should('have.css', 'width', '16px').and('have.css', 'height', '16px');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('reports missing credentials and allows retry without pretending authorization succeeded', () => {
        cy.intercept('POST', '/api/userprofile/qq/start', { statusCode: 503, body: { category: 'not_configured' } }).as('start');
        cy.mount(QQLoginEntry, mountOptions);
        cy.get('.qq-login-entry').click();
        cy.wait('@start').its('request.body').should('deep.equal', { mode: 'login' });
        cy.contains('.el-message', 'QQ application credentials are not configured').should('be.visible');
        cy.get('.qq-login-entry').should('not.be.disabled');
    });

    it('reports unavailable QQ credentials in Spanish with the official badge text', () => {
        const spanish = createI18n({ legacy: false, locale: 'es', messages: { es: i18n.global.getLocaleMessage('es') } });
        cy.intercept('POST', '/api/userprofile/qq/start', { statusCode: 503, body: { category: 'not_configured' } }).as('start');
        cy.mount(QQLoginEntry, { global: { plugins: [spanish] } });
        cy.get('.qq-login-entry').click();
        cy.wait('@start');
        cy.contains('.el-message', 'Las credenciales de la aplicación QQ aún no están configuradas').should('be.visible');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('drops the form divider in compact menu mode', () => {
        cy.mount(QQLoginEntry, { ...mountOptions, props: { compact: true } });
        cy.get('.qq-login-entry').should('have.class', 'qq-login-entry--compact');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });
});
