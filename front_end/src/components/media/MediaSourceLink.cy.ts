import { defineComponent, h } from 'vue';

import MediaSourceLink from './MediaSourceLink.vue';

import i18n from '@/i18n';
import { resetGitHubRepositoryCache } from '@/services/githubService';

const repositoryUrl = 'https://github.com/renamed-owner/renamed-project';

describe('<MediaSourceLink />', () => {
    beforeEach(() => {
        resetGitHubRepositoryCache();
    });

    function mountLink(format = 'g_r', suffix = '42', showGithubDetail = false) {
        cy.mount(defineComponent({
            expose: [],
            render: () => h(MediaSourceLink, { format, suffix, showGithubDetail, 'data-cy': 'source-link' }, { default: () => 'Repository' }),
        }), {
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
        cy.get('@popup').should('have.property', 'opener', null);
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

    it('shows the owner/repo and description when detail display is enabled', () => {
        cy.intercept('GET', 'https://api.github.com/repositories/42', {
            body: { id: 42, full_name: 'renamed-owner/renamed-project', description: 'Minesweeper client', html_url: repositoryUrl },
        }).as('repository');
        mountLink('g_r', '42', true);
        cy.wait('@repository');
        cy.get('a[data-cy=source-link]').should('have.attr', 'href', repositoryUrl).
            and('have.text', 'renamed-owner/renamed-project: Minesweeper client');
        cy.get('@repository.all').should('have.length', 1);
    });

    it('shows only the repo name when the description is empty', () => {
        cy.intercept('GET', 'https://api.github.com/repositories/42', {
            body: { id: 42, full_name: 'renamed-owner/renamed-project', description: '', html_url: repositoryUrl },
        }).as('repository');
        mountLink('g_r', '42', true);
        cy.wait('@repository');
        cy.get('a[data-cy=source-link]').should('have.text', 'renamed-owner/renamed-project');
    });

    it('falls back to the provided title and allows retry when detail loading fails', () => {
        let attempts = 0;
        cy.intercept('GET', 'https://api.github.com/repositories/42', (request) => {
            attempts++;
            request.reply(attempts === 1 ? { statusCode: 403 } : {
                body: { id: 42, full_name: 'renamed-owner/renamed-project', description: 'Ready', html_url: repositoryUrl },
            });
        }).as('repository');
        cy.window().then((win) => {
            cy.stub(win, 'open').returns(null);
        });
        mountLink('g_r', '42', true);
        cy.wait('@repository');
        cy.get('[data-cy=source-link]').should('have.prop', 'tagName', 'BUTTON').and('have.text', 'Repository');
        cy.get('[data-cy=source-link]').click();
        cy.wait('@repository');
        cy.get('a[data-cy=source-link]').should('have.text', 'renamed-owner/renamed-project: Ready');
    });
});
