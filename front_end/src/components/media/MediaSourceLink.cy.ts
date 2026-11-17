import MediaSourceLink from './MediaSourceLink.vue';

import i18n from '@/i18n';

const repositoryUrl = 'https://github.com/renamed-owner/renamed-project';

describe('<MediaSourceLink />', () => {
    function mountLink(format = 'g_r', suffix = '42') {
        cy.mount(MediaSourceLink, {
            props: { format, suffix },
            slots: { default: () => 'Repository' },
            attrs: { 'data-cy': 'source-link' },
            global: { plugins: [i18n] },
        });
    }

    it('resolves only on demand and retains an ordinary link when popups are blocked', () => {
        cy.intercept('GET', 'https://api.github.com/repositories/42', { body: { id: 42, html_url: repositoryUrl } }).as('repository');
        cy.window().then((win) => {
            cy.stub(win, 'open').returns(null);
        });
        mountLink();
        cy.get('@repository.all').should('have.length', 0);
        cy.get('[data-cy=source-link]').should('have.prop', 'tagName', 'BUTTON').click();
        cy.wait('@repository');
        cy.get('a[data-cy=source-link]').should('have.attr', 'href', repositoryUrl).and('have.attr', 'rel', 'noopener noreferrer');
        cy.get('@repository.all').should('have.length', 1);
    });

    it('preopens a window during the gesture and navigates only after validating the URL', () => {
        cy.intercept('GET', 'https://api.github.com/repositories/42', { body: { id: 42, html_url: repositoryUrl } }).as('repository');
        cy.window().then((win) => {
            const navigate = cy.stub().as('navigate');
            const closePopup = cy.stub().as('closePopup');
            const popup = {
                opener: win,
                closed: false,
                document: win.document.implementation.createHTMLDocument(),
                location: { replace: navigate },
                close: closePopup,
            };
            cy.stub(win, 'open').as('open').returns(popup);
            cy.wrap(popup).as('popup');
        });
        mountLink();
        cy.get('[data-cy=source-link]').click();
        cy.get('@open').should('have.been.calledOnceWith', 'about:blank', '_blank');
        cy.wait('@repository');
        cy.get('@popup').its('opener').should('equal', null);
        cy.get('@navigate').should('have.been.calledOnceWith', repositoryUrl);
        cy.get('@closePopup').should('not.have.been.called');
    });

    it('allows retry after a rate limit without producing a fake link', () => {
        let attempts = 0;
        cy.intercept('GET', 'https://api.github.com/repositories/42', (request) => {
            attempts++;
            request.reply(attempts === 1 ? { statusCode: 403 } : { body: { id: 42, html_url: repositoryUrl } });
        }).as('repository');
        cy.window().then((win) => {
            cy.stub(win, 'open').returns(null);
        });
        mountLink();
        cy.get('[data-cy=source-link]').click();
        cy.wait('@repository');
        cy.get('[role=alert]').should('contain', 'Click again to retry');
        cy.get('a[data-cy=source-link]').should('not.exist');
        cy.get('[data-cy=source-link]').should('not.be.disabled').click();
        cy.wait('@repository');
        cy.get('a[data-cy=source-link]').should('have.attr', 'href', repositoryUrl);
        cy.get('[role=alert]').should('not.exist');
    });
});
