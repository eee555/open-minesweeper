import { Key, Lock, User } from '@element-plus/icons-vue';

import LoginForm from './LoginForm.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const mountOptions = {
    global: {
        plugins: [i18n],
        components: { Key, Lock, User },
        config: {
            globalProperties: {
                $axios,
            },
        },
    },
};

function expectCaptchaRefresh(count: number) {
    cy.contains('Captcha').next().find('img').should('have.attr', 'src', `http://127.0.0.1:8000/userprofile/captcha/image/testkey${count}/`);
}

describe('<LoginForm />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/api/accountlink/discord/config', { enabled: false });
        cy.mockLogin();
        cy.mockCaptchaRefresh();
    });

    it('Rendering', () => {
        cy.mount(LoginForm, mountOptions);
        cy.contains('Username').next().find('input').should('have.attr', 'type', 'text');
        cy.contains('Password').next().find('input').should('have.attr', 'type', 'password');
        cy.contains('Captcha').next().find('input').should('have.attr', 'type', 'text');
        cy.contains('Captcha').next().find('img');
        cy.get('.el-input__prefix svg').should('have.length', 3);
        cy.contains('Keep me logged in').find('input').should('have.attr', 'type', 'checkbox');
        cy.contains('Forget password?');
        cy.contains('button', /^Log in$/).should('have.attr', 'type', 'button');
        cy.contains('button', 'Forget password?').should('have.attr', 'type', 'button');
    });

    it('Normal Flow', () => {
        cy.mount(LoginForm, mountOptions);
        cy.contains('Username').next().type('test');
        cy.contains('Password').next().type('test');
        cy.contains('Captcha').next().find('input').type('test');
        cy.contains('Log in').click();

        cy.contains('Invalid captcha. Please input again').should('not.exist');
        cy.contains('Invalid username or password').should('not.exist');
    });

    it('keeps the selected login expiry and resets it when remember-me is unchecked', () => {
        cy.intercept('POST', '/userprofile/login/').as('loginRequest');
        cy.mount(LoginForm, mountOptions);
        cy.contains('Username').next().type('test');
        cy.contains('Password').next().type('test');
        cy.contains('Captcha').next().find('input').type('test');
        cy.get('.rememberMe input').should('not.be.checked');
        cy.get('.rememberMe').click();
        cy.get('.rememberMe input').should('be.checked');
        cy.contains('label', /^30$/).click();
        cy.contains('button', /^Log in$/).click();
        cy.wait('@loginRequest').its('request.body').should((body: string) => {
            expect(new URLSearchParams(body).get('set_expiry')).to.equal('30');
        });
        cy.get('.rememberMe input').focus();
        cy.realPress('Space');
        cy.get('.rememberMe input').should('not.be.checked');
        cy.get('.el-radio-group').should('not.exist');
        cy.contains('button', /^Log in$/).click();
        cy.wait('@loginRequest').its('request.body').should((body: string) => {
            expect(new URLSearchParams(body).get('set_expiry')).to.equal('0');
        });
    });

    it('opens password recovery with the keyboard without submitting the form', () => {
        cy.mount(LoginForm, mountOptions);
        cy.contains('button', 'Forget password?').focus();
        cy.realPress('Enter');
        cy.get('@vue').then((wrapper: ComponentWrapper<typeof LoginForm>) => {
            expect(wrapper.emitted('forgetPassword')).to.have.length(1);
            expect(wrapper.emitted('login')).to.equal(undefined);
        });
        cy.contains('Username required').should('not.exist');
    });

    it('Username Validation', () => {
        cy.mount(LoginForm, mountOptions);

        // Normal username
        cy.contains('Username').next().type('test');
        cy.contains('Username').click();
        cy.contains('Username').next().find('input').should('have.value', 'test');

        // Username required
        cy.contains('Username').next().find('input').clear();
        cy.contains('Username required');

        // Username too long
        cy.contains('Username').next().type('abcdefghijklmnopqrstuvwxyz');
        cy.contains('Username').next().find('input').should('have.value', 'abcdefghijklmnopqrst');
    });

    it('Password Validation', () => {
        cy.mount(LoginForm, mountOptions);

        // Normal password
        cy.contains('Password').next().type('test');
        cy.contains('Password').click();
        cy.contains('Password').next().find('input').should('have.value', 'test');

        // Password required
        cy.contains('Password').next().find('input').clear();
        cy.contains('Password required');
    });

    it('Captcha Validation', () => {
        cy.mount(LoginForm, mountOptions);

        // Normal captcha
        cy.contains('Captcha').next().find('input').type('test');
        cy.contains('Captcha').click();
        cy.contains('Captcha').next().find('input').should('have.value', 'test');

        // Captcha required
        cy.contains('Captcha').next().find('input').clear();
        cy.contains('Captcha required');
    });

    it('Incorrect Captcha', () => {
        cy.mount(LoginForm, mountOptions);
        cy.contains('Username').next().type('test');
        cy.contains('Password').next().type('test');
        cy.contains('Captcha').next().find('input').type('maga');

        cy.contains('Log in').click();
        cy.contains('Invalid captcha. Please input again');
        expectCaptchaRefresh(2);
    });

    it('Incorrect Username or Password', () => {
        cy.mount(LoginForm, mountOptions);
        cy.contains('Username').next().type('test');
        cy.contains('Password').next().type('password');
        cy.contains('Captcha').next().find('input').type('test');

        cy.contains('Log in').click();
        cy.contains('Invalid username or password');
        expectCaptchaRefresh(2);
        cy.contains('Captcha required');
    });
});
