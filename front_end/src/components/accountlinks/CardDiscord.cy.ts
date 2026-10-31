import CardDiscord from './CardDiscord.vue';

import i18n from '@/i18n';
import { AccountDiscord } from '@/utils/accountlinks';

const info = new AccountDiscord({
    id: '803511102246789123',
    parent: 1,
    username: 'discord_user',
    global_name: 'Discord Player',
    update_time: '2026-10-31T12:00:00Z',
    avatar: 'a'.repeat(32),
    banner: 'b'.repeat(32),
    accent_color: 0x5865F2,
    public_flags: 64,
});

describe('<CardDiscord />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/api/accountlink/discord/config', { enabled: true });
        cy.intercept('GET', 'https://cdn.discordapp.com/**', { headers: { 'content-type': 'image/svg+xml' }, body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" />' });
    });

    it('lets moderators inspect the private profile without owner controls', () => {
        cy.mount(CardDiscord, { props: { info, editable: false }, global: { plugins: [i18n] } });
        cy.contains('Discord #803511102246789123');
        cy.contains('Discord Player');
        cy.contains('Private link, visible only to you and site moderators.');
        cy.get('.discord-avatar').should('have.attr', 'src', info.avatarUrl);
        cy.get('.discord-banner').should('have.attr', 'src', info.bannerUrl);
        cy.get('.discord-card').should('have.css', 'border-top-color', 'rgb(88, 101, 242)');
        cy.contains('HypeSquad Bravery');
        cy.get('button').should('not.exist');
    });

    it('explains private visibility before the first authorization', () => {
        cy.mount(CardDiscord, { props: { editable: true }, global: { plugins: [i18n] } });
        cy.contains('Link details are visible only to you and site moderators.');
        cy.contains('button', 'Link Discord');
    });

    it('renders profiles without optional data or image placeholders', () => {
        const account = new AccountDiscord({ id: info.id, parent: 1, username: 'player', global_name: '', update_time: '2026-10-31T12:00:00Z' });
        cy.mount(CardDiscord, { props: { info: account, editable: false }, global: { plugins: [i18n] } });
        cy.contains('player');
        cy.get('.discord-avatar, .discord-banner, .discord-badges').should('not.exist');
    });

    it('unlinks after confirmation and refreshes the parent page', () => {
        cy.intercept('POST', '**/api/accountlink/discord/unlink', { type: 'success' }).as('unlink');
        cy.mount(CardDiscord, { props: { info, editable: true, onRefresh: cy.spy().as('refresh') }, global: { plugins: [i18n] } });
        cy.contains('button', 'Unlink Discord').click();
        cy.contains('.el-message-box button', 'Confirm').click();
        cy.wait('@unlink');
        cy.get('@refresh').should('have.been.calledOnce');
    });
});
