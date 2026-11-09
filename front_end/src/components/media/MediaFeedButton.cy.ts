import MediaFeedButton from './MediaFeedButton.vue';

import $axios from '@/http';
import i18n from '@/i18n';

describe('<MediaFeedButton />', () => {
    it('sends one like per click and throttles rapid clicks', () => {
        cy.clock(Date.now());
        cy.intercept('POST', '/api/media/like', (request) => {
            request.reply({ likes: 1, hot_now: 1, balance: 9, status: 'verified' });
        }).as('like');
        cy.mount(MediaFeedButton, {
            props: { mediaId: 7 },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('button').click();
        cy.wait('@like').its('request.body').should('deep.equal', { media_id: 7 });
        cy.get('button').should('be.disabled');
        cy.tick(1050);
        cy.get('button').should('not.be.disabled').click();
        cy.wait('@like').its('request.body').should('deep.equal', { media_id: 7 });
        cy.get('@like.all').should('have.length', 2);
    });

    it('does not send while disabled', () => {
        cy.intercept('POST', '/api/media/like', { body: { likes: 0, hot_now: 0, balance: 0, status: 'verified' } }).as('like');
        cy.mount(MediaFeedButton, {
            props: { mediaId: 7, disabled: true },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('button').should('be.disabled').click({ force: true });
        cy.get('@like.all').should('have.length', 0);
    });
});
