import EmailNotificationSettings from './EmailNotificationSettings.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import type { UserLanguage } from '@/utils/userprofile';

function mountSettings(mask = 0, staff = true, language: UserLanguage = 'en') {
    cy.then(() => {
        store.login({ id: 42, username: 'self', is_staff: staff, email_notification_mask: mask, language });
    });
    cy.mount(EmailNotificationSettings, {
        global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } },
    });
}

describe('<EmailNotificationSettings />', () => {
    it('reads login preferences and saves only changed types while preserving high bits', () => {
        const mask = 2 ** 31 + 1;
        cy.intercept('PATCH', '/api/userprofile/email-notifications', (request) => {
            expect(request.headers['content-type']).to.include('application/json');
            expect(request.body).to.deep.equal({ changes: [{ type: 'staff_video_plain', enabled: true }] });
            request.reply({ email_notification_mask: mask + 4, language: 'es' });
        }).as('save');
        mountSettings(mask, true, 'es');
        cy.get('select[name=language]').should('have.value', 'es');
        cy.get('input[name=staff_media_review]').should('be.checked');
        cy.contains('button', 'Save').should('be.disabled');
        cy.get('input[name=staff_video_plain]').check();
        cy.contains('button', 'Save').click();
        cy.wait('@save');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(mask + 4);
            expect(store.user.language).to.equal('es');
        });
        cy.contains('button', 'Save').should('be.disabled');
    });

    it('retains edits on failure and prevents duplicate submissions', () => {
        cy.intercept('PATCH', '/api/userprofile/email-notifications', { statusCode: 500, delay: 100, body: {} }).as('failed');
        mountSettings();
        cy.get('select[name=language]').select('zh-cn');
        cy.get('input[name=staff_video_frozen]').check();
        cy.contains('button', 'Save').click();
        cy.contains('button', 'Save').should('be.disabled');
        cy.get('fieldset').should('be.disabled');
        cy.get('select[name=language]').should('be.disabled');
        cy.wait('@failed');
        cy.get('input[name=staff_video_frozen]').should('be.checked');
        cy.get('select[name=language]').should('have.value', 'zh-cn').and('be.enabled');
        cy.contains('button', 'Save').should('be.enabled');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(0);
            expect(store.user.language).to.equal('en');
        });
        cy.closeElNotifications();
    });

    it('discards a response belonging to the previous session', () => {
        cy.intercept('PATCH', '/api/userprofile/email-notifications', (request) => {
            store.login({ id: 43, is_staff: true, email_notification_mask: 16, language: 'es' });
            request.reply({ email_notification_mask: 4, language: 'zh-cn' });
        }).as('previous');
        mountSettings();
        cy.get('input[name=staff_video_plain]').check();
        cy.contains('button', 'Save').click();
        cy.wait('@previous');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(16);
            expect(store.user.language).to.equal('es');
        });
        cy.get('input[name=staff_video_plain]').should('not.be.checked');
        cy.get('input[name=staff_identifier_unsafe]').should('be.checked');
        cy.get('select[name=language]').should('have.value', 'es');
    });

    it('lets ordinary users change language while keeping staff types hidden', () => {
        const mask = 2 ** 31 + 16;
        cy.intercept('PATCH', '/api/userprofile/email-notifications', (request) => {
            expect(request.body).to.deep.equal({ language: 'zh-cn' });
            request.reply({ email_notification_mask: mask, language: 'zh-cn' });
        }).as('language');
        mountSettings(mask, false);
        cy.contains('No email notification types are available yet.').should('be.visible');
        cy.get('input[type=checkbox]').should('not.exist');
        cy.get('select[name=language]').should('have.value', 'en').select('zh-cn');
        cy.contains('button', 'Save').click();
        cy.wait('@language');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(mask);
            expect(store.user.language).to.equal('zh-cn');
        });
        cy.contains('button', 'Save').should('be.disabled');
    });

    it('saves the language and changed notification types together', () => {
        cy.intercept('PATCH', '/api/userprofile/email-notifications', (request) => {
            expect(request.body).to.deep.equal({ changes: [{ type: 'staff_video_plain', enabled: true }], language: 'es' });
            request.reply({ email_notification_mask: 4, language: 'es' });
        }).as('combined');
        mountSettings();
        cy.get('select[name=language]').select('es');
        cy.get('input[name=staff_video_plain]').check();
        cy.contains('button', 'Save').click();
        cy.wait('@combined');
        cy.get('select[name=language]').should('have.value', 'es');
        cy.get('input[name=staff_video_plain]').should('be.checked');
        cy.contains('button', 'Save').should('be.disabled');
    });
});
