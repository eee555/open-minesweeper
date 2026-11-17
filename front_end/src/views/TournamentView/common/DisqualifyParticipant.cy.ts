import DisqualifyParticipant from './DisqualifyParticipant.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { TournamentParticipant } from '@/utils/tournaments';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<DisqualifyParticipant />', () => {
    installHashHistoryCleanup();

    for (const status of ['SUCCESSFUL', 'FAILED'] as const) {
        it(`waits for the worker before reporting ${status}`, () => {
            cy.mockPlayerNameFallback();
            cy.intercept('POST', '**/api/tournament/participant/123/disqualify', { statusCode: 202, body: { id: 'task-123', status: 'READY', traceback: '' } }).as('submit');
            cy.intercept('GET', '**/api/tournament/disqualification-task/task-123', { body: { id: 'task-123', status, traceback: status === 'FAILED' ? 'Task failed' : '' } }).as('task');
            const deleted = cy.spy().as('deleted');
            cy.mount(DisqualifyParticipant, { props: { participant: new TournamentParticipant({ id: 123, user_id: 101 }), onDeleted: deleted }, global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } } });
            cy.get('[data-cy=disqualify-participant]').click();
            cy.get('@submit.all').should('have.length', 0);
            cy.clock(Date.now(), ['setTimeout', 'clearTimeout']);
            cy.contains('.el-dialog button', 'Confirm').click();
            cy.wait('@submit');
            cy.get('@deleted').should('not.have.been.called');
            cy.get('[data-cy=disqualification-status]').should('be.visible').and('contain.text', 'READY');
            cy.tick(1999);
            cy.get('@task.all').should('have.length', 0);
            cy.tick(1);
            cy.wait('@task');
            if (status === 'SUCCESSFUL') cy.get('@deleted').should('have.been.calledOnceWith', 123);
            else {
                cy.get('[data-cy=disqualification-error]').should('be.visible');
                cy.get('@deleted').should('not.have.been.called');
                cy.contains('.el-dialog button', 'Confirm').should('not.be.disabled');
            }
        });
    }
});
