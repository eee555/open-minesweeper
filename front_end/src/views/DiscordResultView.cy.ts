import { createMemoryHistory, createRouter } from 'vue-router';

import DiscordResultView from './DiscordResultView.vue';

import i18n from '@/i18n';

function mountResult(query: string) {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/discord', component: DiscordResultView }] });
    cy.then(() => router.push(`/discord?${query}`));
    cy.mount(DiscordResultView, { global: { plugins: [i18n, router] } });
}

describe('<DiscordResultView />', () => {
    it('links a successful authorization to the site account page', () => {
        mountResult('status=linked&user_id=42');
        cy.contains('Discord account linked');
        cy.contains('a', 'View account links').should('have.attr', 'href', '/player/42/accountlink');
    });

    it('explains that an unlinked account must first be bound', () => {
        mountResult('error=not_linked');
        cy.get('[role="alert"]').should('contain.text', 'Log in with your site account first');
        cy.contains('a', 'View account links').should('not.exist');
    });

    it('does not display arbitrary provider errors or accept contradictory success fields', () => {
        mountResult('status=logged_in&user_id=42&error=private-upstream-detail');
        cy.contains('Discord authorization incomplete');
        cy.get('[role="alert"]').should('contain.text', 'The operation failed.');
        cy.contains('private-upstream-detail').should('not.exist');
    });
});
