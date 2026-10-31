import DiscordAuthorizeButton from './DiscordAuthorizeButton.vue';

import i18n from '@/i18n';

describe('<DiscordAuthorizeButton />', () => {
    it('hides the feature when server credentials are not configured', () => {
        cy.intercept('GET', '**/api/accountlink/discord/config', { enabled: false }).as('config');
        cy.mount(DiscordAuthorizeButton, { props: { mode: 'login' }, global: { plugins: [i18n] } });
        cy.wait('@config');
        cy.contains('button', 'Log in with Discord').should('not.exist');
    });

    it('preserves remember-me settings and displays recoverable failures', () => {
        cy.intercept('GET', '**/api/accountlink/discord/config', { enabled: true });
        cy.intercept('POST', '**/api/accountlink/discord/start', {
            statusCode: 403, body: { type: 'error', object: 'discord', category: 'session_changed' },
        }).as('start');
        cy.mount(DiscordAuthorizeButton, { props: { mode: 'login', setExpiry: 30 }, global: { plugins: [i18n] } });
        cy.contains('button', 'Log in with Discord').click();
        cy.wait('@start').its('request.body').should('equal', 'mode=login&set_expiry=30');
        cy.get('[role="alert"]').should('contain.text', 'Your site login session changed.');
        cy.contains('button', 'Log in with Discord').should('not.be.disabled');
    });
});
