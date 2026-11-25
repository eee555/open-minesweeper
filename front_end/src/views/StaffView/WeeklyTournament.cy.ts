import WeeklyTournament from './WeeklyTournament.vue';

import $axios from '@/http';
import i18n from '@/i18n';

describe('<WeeklyTournament />', () => {
    it('lets staff select one of four speed formats and displays the created format', () => {
        cy.intercept('POST', '**/api/tournament/weekly/new', {
            body: { data: { id: 8, year: 2026, week: 48, state: 'n', start_time: '2026-11-23T00:00:00Z', end_time: '2026-11-30T00:00:00Z', tournament_format: 'f' } },
        }).as('create');
        cy.mount(WeeklyTournament, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('[data-cy=weekly-format]').should('have.value', 'c').find('option').should(($options) => {
            expect(Array.from($options, (option) => option.textContent?.trim())).to.deep.equal(['Classic', 'NF', 'Hardcore NG', 'Hardcore NG NF']);
        });
        cy.get('[data-cy=weekly-format]').select('f');
        cy.contains('button', 'Create next week').click();
        cy.wait('@create').its('request.body').should('equal', 'tournament_format=f');
        cy.get('[data-cy=weekly-result]').should('contain.text', 'Hardcore NG NF');
        cy.get('[data-cy=weekly-kind]').select('weekly-eff');
        cy.get('[data-cy=weekly-format]').should('not.exist');
    });
});
