import { ElMessage } from 'element-plus';
import { createI18n } from 'vue-i18n';

import QQLoginEntry from './QQLoginEntry.vue';

import i18n from '@/i18n';

describe('<QQLoginEntry />', () => {
    afterEach(() => {
        ElMessage.closeAll();
    });

    it('renders the official 16×16 badge with fixed Chinese text', () => {
        cy.mount(QQLoginEntry, { global: { plugins: [i18n] } });
        cy.get('.qq-login-entry img').should('have.attr', 'src', `${import.meta.env.BASE_URL}img/qq_login_16x16.png`).and('have.attr', 'width', '16').and('have.attr', 'height', '16').and('have.attr', 'alt', '');
        cy.get('.qq-login-entry img').should('have.css', 'width', '16px').and('have.css', 'height', '16px');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('shows the pending sign-in message in Spanish and keeps the official badge text', () => {
        const spanish = createI18n({ legacy: false, locale: 'es' });
        cy.mount(QQLoginEntry, { global: { plugins: [spanish] } });
        cy.get('.qq-login-entry').click();
        cy.contains('.el-message', 'El acceso con QQ aún no está disponible').should('be.visible');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('drops the form divider in compact menu mode', () => {
        cy.mount(QQLoginEntry, { global: { plugins: [i18n] }, props: { compact: true } });
        cy.get('.qq-login-entry').should('have.class', 'qq-login-entry--compact');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });
});
