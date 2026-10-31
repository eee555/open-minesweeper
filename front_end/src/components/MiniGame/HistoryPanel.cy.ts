import HistoryPanel from './HistoryPanel.vue';

import i18n from '@/i18n';
import { getMinigameDatabase, MINIGAME_RESULTS_STORE, saveMinigameResult } from '@/utils/minigame/history';
import { leftClickModes } from '@/utils/minigame/leftClickTraining';
import { isolateMinigameHistory } from '@cy/support/minigame';

describe('local minigame history', () => {
    isolateMinigameHistory();

    it('filters inclusive calendar dates, sorts times, and plays a row with mouse or keyboard', () => {
        const ids: number[] = [];
        cy.then(async () => {
            const db = await getMinigameDatabase();
            // Match the browser-local calendar boundaries used by the date inputs.
            for (const [date, scoreMs] of [['2026-10-29T23:59:59.999', 100], ['2026-10-30T00:00:00', 300], ['2026-10-30T23:59:59.999', 200], ['2026-10-31T00:00:00', 400]] as const) {
                ids.push(await db.add(MINIGAME_RESULTS_STORE, { game: 'left-click', mode: leftClickModes[0], playedAt: new Date(date).getTime(), scoreMs, replay: new ArrayBuffer(0) }));
            }
        });
        const play = cy.stub().as('play');
        cy.mount(HistoryPanel, { props: { rankingKey: leftClickModes[0].rankingKey, onPlay: play }, global: { plugins: [i18n] } });
        cy.get('.history-row').should('have.length', 4);
        cy.get('[data-cy=minigame-history-from]').type('2026-10-30');
        cy.get('[data-cy=minigame-history-to]').type('2026-10-30');
        cy.get('.history-row').should('have.length', 2);
        cy.get('[data-cy=minigame-history-score-sort]').click();
        cy.get('table').extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[1])).to.deep.equal(['0.200', '0.300']);
        });
        cy.get('.history-row').first().click();
        cy.get('@play').should('have.been.calledOnce');
        cy.then(() => {
            expect(play.firstCall.args).to.deep.equal([ids[2]]);
        });
        cy.get('[data-cy=minigame-history-score-sort]').click();
        cy.get('table').extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[1])).to.deep.equal(['0.300', '0.200']);
        });
        cy.get('.history-row').first().focus();
        cy.get('.history-row').first().type('{enter}');
        cy.get('@play').should('have.been.calledTwice');
        cy.get('[data-cy=minigame-history-from]').clear();
        cy.get('[data-cy=minigame-history-to]').clear();
        cy.get('.history-row').should('have.length', 4);
        cy.get('[data-cy=minigame-history-date-sort]').click();
        cy.then(() => {
            cy.get('.history-row').first().should('have.attr', 'data-history-id', String(ids[3]));
        });
    });

    it('paginates matching records and resets the page when the configuration changes or a result commits', () => {
        cy.then(async () => {
            const db = await getMinigameDatabase();
            const tx = db.transaction(MINIGAME_RESULTS_STORE, 'readwrite');
            for (let i = 0; i < 21; i++) {
                await tx.store.add({ game: 'left-click', mode: leftClickModes[0], playedAt: i, scoreMs: 1000, replay: new ArrayBuffer(0) });
            }
            await tx.store.add({ game: 'left-click', mode: leftClickModes[1], playedAt: 30, scoreMs: 5, replay: new ArrayBuffer(0) });
            await tx.done;
        });
        cy.mount(HistoryPanel, { props: { rankingKey: leftClickModes[0].rankingKey }, global: { plugins: [i18n] } });
        cy.get('.history-row').should('have.length', 20);
        cy.get('[data-cy=minigame-history-pagination] .btn-next').click();
        cy.get('.history-row').should('have.length', 1);
        cy.get('@vue').invoke('setProps', { rankingKey: leftClickModes[1].rankingKey });
        cy.get('table').extractTableData().should((rows) => {
            expect(rows).to.have.length(2);
            expect(rows[1][1]).to.equal('0.005');
        });
        cy.get('@vue').invoke('setProps', { rankingKey: leftClickModes[0].rankingKey });
        cy.get('.history-row').should('have.length', 20);
        cy.get('[data-cy=minigame-history-pagination] .btn-next').click();
        cy.get('.history-row').should('have.length', 1);
        cy.then(() => saveMinigameResult({ game: 'left-click', mode: leftClickModes[0], scoreMs: 1234, replay: { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [], specialEvents: [] } }));
        cy.get('.history-row').should('have.length', 20);
        cy.get('table').extractTableData().should((rows) => {
            expect(rows[1][1]).to.equal('1.234');
        });
    });
});
