import DeleteVideos from './DeleteVideos.vue';

import $axios from '@/http';
import i18n from '@/i18n';

function mountPage() {
    cy.mount(DeleteVideos, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    cy.wait('@access');
}

describe('superuser video deletion page', () => {
    it('hides deletion controls when the backend denies superuser access', () => {
        cy.intercept('GET', '/api/video/admin/delete', { statusCode: 401, body: { detail: 'Unauthorized' } }).as('access');
        mountPage();
        cy.get('[data-cy=delete-access-error]').should('contain.text', 'requires a signed-in superuser');
        cy.get('[data-cy=delete-ids]').should('not.exist');
        cy.get('[data-cy=delete-start]').should('not.exist');
    });

    it('requires confirmation, deduplicates IDs, stops on failure and resumes only remaining requests', () => {
        cy.intercept('GET', '/api/video/admin/delete', { csrf_token: 'token' }).as('access');
        const requests: number[] = [];
        let failed = false;
        cy.intercept('POST', '/api/video/admin/delete', (request) => {
            const { id } = request.body as { id: number };
            requests.push(id);
            expect(request.headers['x-csrftoken']).to.equal('token');
            if (id === 22 && !failed) {
                failed = true;
                request.reply({ statusCode: 504, body: {} });
            } else {
                request.reply({ id, deleted: id !== 22, affected_tournament_ids: id === 11 ? [7] : [] });
            }
        }).as('deleteOne');
        mountPage();
        cy.get('[data-cy=delete-warning]').should('contain.text', 'not recalculated automatically');
        cy.get('[data-cy=delete-ids]').type('11,22,11,33');
        cy.get('[data-cy=delete-start]').should('be.disabled');
        cy.get('[data-cy=delete-confirm]').check();
        cy.get('[data-cy=delete-start]').click();
        cy.wait('@deleteOne');
        cy.wait('@deleteOne');
        cy.get('[data-cy=delete-error]').should('contain.text', 'replay 22').and('contain.text', 'Further requests have stopped');
        cy.get('[data-cy=delete-progress]').should('contain.text', 'Confirmed 1 / 3');
        cy.then(() => {
            expect(requests).to.deep.equal([11, 22]);
        });
        cy.get('[data-cy=delete-start]').should('be.disabled');
        cy.get('[data-cy=delete-confirm]').check();
        cy.get('[data-cy=delete-start]').click();
        cy.wait('@deleteOne');
        cy.wait('@deleteOne');
        cy.get('[data-cy=delete-progress]').should('contain.text', 'Confirmed 3 / 3').and('contain.text', '1 already absent');
        cy.then(() => {
            expect(requests).to.deep.equal([11, 22, 22, 33]);
        });
        cy.get('[data-cy=delete-results] tbody tr').should('have.length', 3);
        cy.get('[data-cy=delete-start]').should('be.disabled');
    });

    it('does not enable deletion when any ID is invalid', () => {
        cy.intercept('GET', '/api/video/admin/delete', { csrf_token: 'token' }).as('access');
        mountPage();
        cy.get('[data-cy=delete-ids]').type('11,0,22');
        cy.get('[data-cy=delete-confirm]').check();
        cy.get('[data-cy=delete-start]').should('be.disabled');
        cy.get('form [role=alert]').should('contain.text', 'all IDs are valid');
    });

    it('finishes the current request before stopping the remaining queue', () => {
        cy.intercept('GET', '/api/video/admin/delete', { csrf_token: 'token' }).as('access');
        const requests: number[] = [];
        let release: (() => void) | undefined;
        cy.intercept('POST', '/api/video/admin/delete', (request) => new Promise<void>((resolve) => {
            const { id } = request.body as { id: number };
            requests.push(id);
            release = () => {
                request.reply({ id, deleted: true, affected_tournament_ids: [] });
                resolve();
            };
        })).as('deleteOne');
        mountPage();
        cy.get('[data-cy=delete-ids]').type('11,22');
        cy.get('[data-cy=delete-confirm]').check();
        cy.get('[data-cy=delete-start]').click();
        cy.get('[data-cy=delete-current]').should('contain.text', '11');
        cy.get('[data-cy=delete-stop]').click();
        cy.then(() => {
            release?.();
        });
        cy.wait('@deleteOne');
        cy.get('[data-cy=delete-progress]').should('contain.text', 'Confirmed 1 / 2');
        cy.get('[data-cy=delete-start]').should('contain.text', 'Continue deleting the remaining 1').and('not.be.disabled');
        cy.then(() => {
            expect(requests).to.deep.equal([11]);
        });
    });
});
