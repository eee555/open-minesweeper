import HistoryImport from './HistoryImport.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<GSC HistoryImport />', () => {
    installHashHistoryCleanup();

    function mountHistory(hostId: number) {
        cy.mockPlayerNameFallback();
        store.login({ id: 99, username: 'history-admin', realname: 'Host', is_staff: true });
        const participant = { id: 123, user_id: 0, manual_scores: true, arbiter_identifier: 'Anonymous Player', has_videos: false, bt20sum: 1000, it12sum: 2000, et5sum: 3000 };
        cy.intercept('GET', '**/api/tournament/gsc/admin-info?*', { body: { id: 42, host_id: hostId, order: 19, state: 'a', end_time: '2020-01-01T00:00:00Z' } }).as('historyInfo');
        cy.intercept('GET', '**/api/tournament/gsc/results?*', { body: [participant, { ...participant, id: 124, user_id: 987654, has_videos: true }] }).as('history');
        cy.intercept('POST', '**/api/tournament/participant/123/disqualify', { statusCode: 202, body: { id: 'task-1', status: 'READY', traceback: '' } }).as('disqualify');
        cy.intercept('GET', '**/api/tournament/disqualification-task/task-1', { body: { id: 'task-1', status: 'SUCCESSFUL', traceback: '' } }).as('task');
        cy.mount(HistoryImport, { props: { order: 19 }, global: { plugins: [pinia, i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait(['@historyInfo', '@history']);
    }

    it('shows host disqualification for participants with and without videos', () => {
        mountHistory(99);
        cy.get('[data-cy=history-participants] table').getTable().should((rows) => {
            expect(rows).to.have.length(2);
            expect(rows[0]).to.include({ Player: 'Anonymous Player', 'Score source': 'Manual', Replay: 'None', 'Total / ms': '6000' });
            expect(rows[1].Player).to.equal('User#987654');
        });
        cy.get('[data-cy=disqualify-participant]').should('have.length', 2).first().click();
        cy.get('@disqualify.all').should('have.length', 0);
        cy.contains('.el-dialog button', 'Confirm').click();
        cy.wait('@disqualify');
        cy.get('[data-cy=disqualification-status]').should('be.visible');
        cy.wait('@task');
        cy.wait(['@historyInfo', '@history']);
    });

    it('does not grant a non-host administrator the disqualification action', () => {
        mountHistory(100);
        cy.get('[data-cy=history-participants] table').getTable().should('have.length', 2);
        cy.get('[data-cy=disqualify-participant]').should('not.exist');
    });
});
