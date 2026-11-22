import EmailNotificationSettings from './EmailNotificationSettings.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';

function mountSettings(mask = 0, staff = true) {
    cy.then(() => {
        store.login({ id: 42, username: 'self', is_staff: staff, email_notification_mask: mask });
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
            request.reply({ email_notification_mask: mask + 4 });
        }).as('save');
        mountSettings(mask);
        cy.get('input[name=staff_media_review]').should('be.checked');
        cy.contains('button', 'Save').should('be.disabled');
        cy.get('input[name=staff_video_plain]').check();
        cy.contains('button', 'Save').click();
        cy.wait('@save');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(mask + 4);
        });
        cy.contains('button', 'Save').should('be.disabled');
    });

    it('retains edits on failure and prevents duplicate submissions', () => {
        cy.intercept('PATCH', '/api/userprofile/email-notifications', { statusCode: 500, delay: 100, body: {} }).as('failed');
        mountSettings();
        cy.get('input[name=staff_video_frozen]').check();
        cy.contains('button', 'Save').click();
        cy.contains('button', 'Save').should('be.disabled');
        cy.get('fieldset').should('be.disabled');
        cy.wait('@failed');
        cy.get('input[name=staff_video_frozen]').should('be.checked');
        cy.contains('button', 'Save').should('be.enabled');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(0);
        });
        cy.closeElNotifications();
    });

    it('discards a response belonging to the previous session', () => {
        cy.intercept('PATCH', '/api/userprofile/email-notifications', (request) => {
            store.login({ id: 43, is_staff: true, email_notification_mask: 16 });
            request.reply({ email_notification_mask: 4 });
        }).as('previous');
        mountSettings();
        cy.get('input[name=staff_video_plain]').check();
        cy.contains('button', 'Save').click();
        cy.wait('@previous');
        cy.then(() => {
            expect(store.user.email_notification_mask).to.equal(16);
        });
        cy.get('input[name=staff_video_plain]').should('not.be.checked');
        cy.get('input[name=staff_identifier_unsafe]').should('be.checked');
    });

    it('shows an empty type list to ordinary users', () => {
        mountSettings(0, false);
        cy.contains('No email notification types are available yet.').should('be.visible');
        cy.get('input[type=checkbox]').should('not.exist');
    });
});
