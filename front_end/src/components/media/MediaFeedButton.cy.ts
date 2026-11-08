import MediaFeedButton from './MediaFeedButton.vue';

import $axios from '@/http';
import i18n from '@/i18n';

describe('<MediaFeedButton />', () => {
    it('accumulates clicks within one second into a single request', () => {
        cy.clock(Date.now());
        cy.intercept('POST', '/api/media/like', (request) => {
            request.reply({ likes: 3, hot_now: 2.5, balance: 7, status: 'verified' });
        }).as('like');
        cy.mount(MediaFeedButton, {
            props: { mediaId: 7 },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('button').click();
        cy.get('button').click();
        cy.get('button').click();
        cy.get('button').should('contain.text', '+3');
        cy.tick(1000);
        cy.wait('@like').its('request.body').should('deep.equal', { media_id: 7, count: 3 });
        cy.get('button').should('not.contain.text', '+3');
    });

    it('does not accumulate clicks while disabled', () => {
        cy.clock(Date.now());
        cy.intercept('POST', '/api/media/like', { body: { likes: 0, hot_now: 0, balance: 0, status: 'verified' } }).as('like');
        cy.mount(MediaFeedButton, {
            props: { mediaId: 7, disabled: true },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('button').should('be.disabled').click({ force: true });
        cy.tick(2000);
        cy.get('@like.all').should('have.length', 0);
    });
});
