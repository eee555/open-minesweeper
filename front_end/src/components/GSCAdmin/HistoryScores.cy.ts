import { gscScoreFields, historyCsvHeaders } from './history';
import type { HistoryScoreRow } from './history';
import HistoryScores from './HistoryScores.vue';

import i18n from '@/i18n';

function csv(count: number) {
    return [historyCsvHeaders('users').join(','), ...Array.from({ length: count }, (_, i) => [19, 101 + i, ...gscScoreFields.map(() => 1000)].join(','))].join('\n');
}

describe('<GSC HistoryScores />', () => {
    it('submits ten-row batches sequentially and stops on failure without retrying an uncertain request', () => {
        const batches: number[] = [];
        let completed = false;
        cy.intercept('POST', '**/api/tournament/gsc/history/scores/users', (request) => {
            const body = request.body as { order: number; rows: HistoryScoreRow[] };
            batches.push(body.rows.length);
            if (batches.length === 1) {
                request.on('before:response', () => {
                    completed = true;
                });
                request.reply({ delay: 100, body: 10 });
            } else {
                expect(completed).to.equal(true);
                request.reply({ statusCode: 409, body: { detail: 'Already registered' } });
            }
        }).as('batch');
        cy.mount(HistoryScores, { global: { plugins: [i18n] }, props: { kind: 'users' } });
        cy.get('[data-cy=history-csv]').selectFile({ contents: Cypress.Buffer.from(csv(21)), fileName: 'scores.csv' });
        cy.get('[data-cy=history-csv-submit]').should('contain.text', '21').click();
        cy.wait('@batch');
        cy.wait('@batch');
        cy.get('[data-cy=history-csv-progress]').should('contain.text', '10 / 21');
        cy.get('[data-cy=history-csv-error]').should('contain.text', '12, 13').and('contain.text', 'Later batches were not submitted');
        cy.get('[data-cy=history-csv-submit]').should('be.disabled');
        cy.then(() => expect(batches).to.deep.equal([10, 10]));
    });

    it('rejects malformed files before any request and accepts the headered anonymous fixture', () => {
        cy.intercept('POST', '**/api/tournament/gsc/history/scores/anonymous', { body: 10 }).as('anonymous');
        cy.mount(HistoryScores, { global: { plugins: [i18n] }, props: { kind: 'anonymous' } });
        cy.get('[data-cy=history-csv]').selectFile({ contents: Cypress.Buffer.from('19,unheadered,1000'), fileName: 'invalid.csv' });
        cy.get('[data-cy=history-csv-error]').should('contain.text', 'headers');
        cy.get('[data-cy=history-csv-submit]').should('be.disabled');
        cy.get('@anonymous.all').should('have.length', 0);
        cy.get('[data-cy=history-csv]').selectFile('cypress/fixtures/gsc/type3.csv');
        cy.get('[data-cy=history-csv-submit]').should('contain.text', '10').click();
        cy.wait('@anonymous').its('request.body.rows.0.arbiter_identifier').should('eq', 'kiraa96G09511');
    });
});
