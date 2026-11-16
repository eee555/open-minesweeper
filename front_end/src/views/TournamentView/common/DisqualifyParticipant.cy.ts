import DisqualifyParticipant from './DisqualifyParticipant.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { TournamentParticipant } from '@/utils/tournaments';

describe('<DisqualifyParticipant />', () => {
    for (const status of ['SUCCESSFUL', 'FAILED'] as const) {
        it(`waits for the worker before reporting ${status}`, () => {
            cy.mockPlayerNameFallback();
            cy.intercept('POST', '**/api/tournament/participant/123/disqualify', { statusCode: 202, body: { id: 'task-123', status: 'READY', traceback: '' } }).as('submit');
            cy.intercept('GET', '**/api/tournament/disqualification-task/task-123', { body: { id: 'task-123', status, traceback: status === 'FAILED' ? 'Task failed' : '' } }).as('task');
            const deleted = cy.spy().as('deleted');
            cy.mount(DisqualifyParticipant, { props: { participant: new TournamentParticipant({ id: 123, user_id: 101 }), onDeleted: deleted }, global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
            cy.get('[data-cy=disqualify-participant]').click();
            cy.get('@submit.all').should('have.length', 0);
            cy.contains('.el-dialog button', 'Confirm').click();
            cy.wait('@submit');
            cy.get('@deleted').should('not.have.been.called');
            cy.get('[data-cy=disqualification-status]').should('be.visible');
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
