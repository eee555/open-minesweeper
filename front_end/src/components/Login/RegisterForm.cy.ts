import { Key, Lock, Message, User } from '@element-plus/icons-vue';

import RegisterForm from './RegisterForm.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const mountOptions = {
    global: {
        plugins: [i18n],
        components: { Key, Lock, Message, User },
        config: {
            globalProperties: {
                $axios,
            },
        },
    },
};

const errorColor = 'rgb(245, 108, 108)';
const successColor = 'rgb(168, 171, 178)';

function findUsernameInput() {
    return cy.contains('Username').next().find('input');
}
function findEmailInput() {
    return cy.contains('Email').next().find('input');
}
function findPasswordInput() {
    return cy.contains('Password').next().find('input');
}
function findConfirmPasswordInput() {
    return cy.contains('Confirm password').next().find('input');
}
function findRegisterButton() {
    return cy.get('button').filter(':contains("Register")');
}

function expectEmailValidationError(msg: string) {
    cy.get('[data-cy=emailFormItem]').contains(msg).should('have.css', 'color', errorColor);
}
function expectEmailValidationSuccess() {
    cy.get('[data-cy=emailFormItem]').find('i').last().should('have.css', 'color', successColor);
}
function expectUsernameValidationError(msg: string) {
    cy.get('[data-cy=usernameFormItem]').contains(msg).should('have.css', 'color', errorColor);
}
function expectUsernameValidationSuccess() {
    cy.get('[data-cy=usernameFormItem]').find('i').last().should('have.css', 'color', successColor);
}

function mockCheckCollision() {
    cy.intercept('GET', '/userprofile/checkcollision/*', (req) => {
        const params = req.query;
        if (params.username === 'existingUsername' || params.email === 'existing@email.com') {
            req.reply({
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: 'True',
            });
        } else {
            req.reply({
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: 'False',
            });
        }
    }).as('checkCollision');
}

describe('<RegisterForm />', () => {
    beforeEach(() => {
        cy.mockCaptchaRefresh();
        mockCheckCollision();
    });

    it('Rendering', () => {
        cy.mount(RegisterForm, mountOptions);
        cy.contains('Register').find('button').should('not.exist');
        findRegisterButton().should('be.disabled');
        findUsernameInput().should('have.attr', 'type', 'text');
        findEmailInput().should('have.attr', 'type', 'email');
        cy.contains('Image captcha').next().find('input').should('have.attr', 'type', 'text');
        cy.contains('Image captcha').next().find('img');
        cy.contains('Email code').next().find('input').should('have.attr', 'type', 'text');
        cy.contains('Email code').next().find('button').should('have.text', 'Send');
        findPasswordInput().should('have.attr', 'type', 'password');
        findConfirmPasswordInput().should('have.attr', 'type', 'password');
        cy.get('.el-input__prefix svg').should('have.length', 6);
        cy.contains('Agree to').find('input').should('have.attr', 'type', 'checkbox');
    });

    it('keeps the agreement link separate from the checkbox and supports Space', () => {
        cy.mount(RegisterForm, mountOptions);
        cy.get('input[name=checkoutSecret]').should('not.be.checked');
        cy.contains('a', 'Terms & Conditions').should('have.attr', 'target', '_blank').and('have.attr', 'rel', 'noopener noreferrer');
        cy.contains('a', 'Terms & Conditions').parents('label').should('not.exist');
        cy.contains('label', 'Agree to').click();
        cy.get('input[name=checkoutSecret]').should('be.checked').focus();
        cy.realPress('Space');
        cy.get('input[name=checkoutSecret]').should('not.be.checked');
        findRegisterButton().should('be.disabled');
    });

    it('Username Validation - Collision', () => {
        cy.mount(RegisterForm, mountOptions);

        findUsernameInput().type('existingUsername{enter}');
        expectUsernameValidationError('Username already exists');

        findUsernameInput().clear();
        findUsernameInput().type('newUsername{enter}');
        expectUsernameValidationSuccess();
    });

    it('Email Validation - Format', () => {
        cy.mount(RegisterForm, mountOptions);
        findEmailInput().type('a{enter}');
        expectEmailValidationError('Invalid email address');

        findEmailInput().clear();
        findEmailInput().type('a@b{enter}');
        expectEmailValidationError('Invalid email address');

        findEmailInput().clear();
        expectEmailValidationError('Email required');
    });

    it('Email Validation - Collision', () => {
        cy.mount(RegisterForm, mountOptions);
        findEmailInput().type('existing@email.com{enter}');
        expectEmailValidationError('Email already exists');

        findEmailInput().clear();
        findEmailInput().type('new@email.com{enter}');
        expectEmailValidationSuccess();
    });

    it('Normal Flow', () => {
        cy.mockGetEmailCode();
        cy.mockRegister();
        cy.mount(RegisterForm, mountOptions);

        findRegisterButton().should('be.disabled');

        findUsernameInput().type('validUsername{enter}');
        findRegisterButton().should('be.disabled');

        findEmailInput().type('valid@email.com{enter}');
        findRegisterButton().should('be.disabled');

        cy.contains('Image captcha').next().find('input').type('test{enter}');
        cy.get('button').contains('Send').click();
        cy.contains('Email code').next().find('input').should('be.enabled');
        cy.contains('Email code').next().find('input').type('123456{enter}');
        findRegisterButton().should('be.disabled');

        findPasswordInput().type('validPassword{enter}');
        findRegisterButton().should('be.disabled');

        findConfirmPasswordInput().type('validPassword{enter}');
        findRegisterButton().should('be.disabled');

        cy.contains('Agree to').find('input').parent().click();
        findRegisterButton().should('be.enabled');

        findRegisterButton().click();
        cy.contains('Successfully registered!');
    });

    for (const category of ['illegal', 'unknown']) {
        it(`checks username moderation only on submission and handles ${category}`, () => {
            cy.mockGetEmailCode();
            cy.intercept('POST', '/api/userprofile/register', {
                body: { type: 'error', object: 'censorship', category },
            }).as('registerRequest');
            const onLogin = cy.spy().as('registered');
            cy.mount(RegisterForm, { ...mountOptions, props: { onLogin } });

            findUsernameInput().type('validUsername{enter}');
            findEmailInput().type('valid@email.com{enter}');
            cy.contains('Image captcha').next().find('input').type('test{enter}');
            cy.contains('button', 'Send').click();
            cy.contains('Email code').next().find('input').type('123456{enter}');
            findPasswordInput().type('validPassword{enter}');
            findConfirmPasswordInput().type('validPassword{enter}');
            cy.contains('label', 'Agree to').click();

            findRegisterButton().should('be.enabled');
            cy.get('@registerRequest.all').should('have.length', 0);
            findRegisterButton().click();
            cy.wait('@registerRequest');
            cy.get('@registered').should('not.have.been.called');
            cy.contains('Email code').next().find('input').should('have.value', '123456');
            if (category === 'illegal') {
                expectUsernameValidationError('This username did not pass content moderation. Please choose another username.');
                findRegisterButton().should('be.disabled');
            } else {
                cy.contains('.el-notification', 'Username moderation is temporarily unavailable. Please try again later.').should('be.visible');
                findRegisterButton().should('be.enabled');
                cy.closeElNotifications();
            }
        });
    }

    // 这个不放到最后就会出奇怪的bug
    it('Username Validation - Format', () => {
        cy.mount(RegisterForm, mountOptions);

        cy.log('Empty username');
        findUsernameInput().type('a');
        findUsernameInput().clear();
        expectUsernameValidationError('Username required');
        findRegisterButton().should('be.disabled');

        cy.log('Starts with space');
        findUsernameInput().clear();
        findUsernameInput().realType(' a');
        expectUsernameValidationError('Username cannot start or end with space characters');

        cy.log('Starts with mark');
        findUsernameInput().clear();
        findUsernameInput().invoke('val', '\u0301');
        findUsernameInput().type('a');
        expectUsernameValidationError('Username cannot start with mark characters');

        cy.log('Ends with space');
        findUsernameInput().clear();
        findUsernameInput().realType('a ');
        expectUsernameValidationError('Username cannot start or end with space characters');

        cy.log('Contains control');
        findUsernameInput().clear();
        findUsernameInput().invoke('val', '\t');
        findUsernameInput().realType('a');
        expectUsernameValidationError('Username cannot contain control characters');

        cy.log('Contains line separator');
        findUsernameInput().clear();
        findUsernameInput().invoke('val', '\u2028');
        findUsernameInput().realType('a');
        expectUsernameValidationError('Username cannot contain line separators');

        cy.log('Contains paragraph separator');
        findUsernameInput().clear();
        findUsernameInput().invoke('val', '\u2029');
        findUsernameInput().realType('a');
        expectUsernameValidationError('Username cannot contain paragraph separators');
    });

    // Email code validation is handled in emailCodeBlock.cy.ts
    // Password validation is handled in passwordConfirmBlock.cy.ts
});
