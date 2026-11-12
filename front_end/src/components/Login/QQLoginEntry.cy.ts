import { ElMessage } from 'element-plus';

import QQLoginEntry from './QQLoginEntry.vue';

describe('<QQLoginEntry />', () => {
    afterEach(() => {
        ElMessage.closeAll();
    });

    it('renders the official 16×16 badge with fixed Chinese text', () => {
        cy.mount(QQLoginEntry);
        cy.get('.qq-login-entry img').should('have.attr', 'src', `${import.meta.env.BASE_URL}img/qq_login_16x16.png`).and('have.attr', 'width', '16').and('have.attr', 'height', '16').and('have.attr', 'alt', '');
        cy.get('.qq-login-entry img').should('have.css', 'width', '16px').and('have.css', 'height', '16px');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });

    it('explains in Chinese that QQ login is not available yet without navigating away', () => {
        cy.mount(QQLoginEntry);
        cy.get('.qq-login-entry').click();
        cy.contains('.el-message', 'QQ 登录尚未开放').should('be.visible');
    });

    it('drops the form divider in compact menu mode', () => {
        cy.mount(QQLoginEntry, { props: { compact: true } });
        cy.get('.qq-login-entry').should('have.class', 'qq-login-entry--compact');
        cy.get('.qq-login-label').should('have.text', 'QQ登录');
    });
});
