import Minigame from './Minigame.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { installAdminCsrfInterceptor } from '@/services/adminCsrf';

const firstKey = 'left-click-b-50-v1';
const secondKey = 'left-click-b-75-v1';
const score = { score: 1234, achieved_at: '2026-10-30T10:00:00+08:00' };
let csrfInterceptor: number;

function loadRecords() {
    cy.intercept('GET', '/api/minigame/left-click/player/42', { player_id: 42, records: { [firstKey]: score, [secondKey]: score } }).as('records');
    cy.mount(Minigame, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    cy.get('[data-cy=minigame-player-id] input').type('42');
    cy.get('[data-cy=minigame-query]').click();
    cy.wait('@records');
    cy.get('[data-cy=minigame-records] tbody tr').should('have.length', 2);
}

describe('staff minigame record deletion', () => {
    beforeEach(() => {
        cy.clearCookie('csrftoken');
        csrfInterceptor = installAdminCsrfInterceptor($axios, () => true);
        cy.intercept('GET', '/api/userprofile/admin/csrf', { csrf_token: 'staff-token' }).as('csrf');
    });

    afterEach(() => {
        $axios.interceptors.request.eject(csrfInterceptor);
    });

    it('confirms the player and ranking, supplies CSRF, and removes only the selected row', () => {
        cy.intercept('DELETE', `/api/minigame/admin/${firstKey}/player/42`, { statusCode: 204, body: '' }).as('delete');
        loadRecords();
        cy.get(`[data-ranking-key=${firstKey}] [data-cy=minigame-delete]`).click();
        cy.get('.el-message-box').should('contain.text', '42').and('contain.text', firstKey);
        cy.get('.el-message-box__btns button').first().click();
        cy.get('@delete.all').should('have.length', 0);
        cy.get(`[data-ranking-key=${firstKey}] [data-cy=minigame-delete]`).click();
        cy.get('.el-message-box__btns button').last().click();
        cy.wait('@csrf');
        cy.wait('@delete').its('request.headers.x-csrftoken').should('equal', 'staff-token');
        cy.get(`[data-ranking-key=${firstKey}]`).should('not.exist');
        cy.get(`[data-ranking-key=${secondKey}]`).should('contain.text', '1.234');
        cy.closeElNotifications();

        cy.intercept('GET', '/api/minigame/flag-chord/player/42', { player_id: 42, records: { 'flag-chord-b-v1': score } }).as('chordRecords');
        cy.get('[data-cy=minigame-game]').click();
        cy.get('.el-select-dropdown__item').filter(':visible').contains(i18n.global.t('minigame.flag-chord')).click();
        cy.get('[data-cy=minigame-records]').should('not.exist');
        cy.get('[data-cy=minigame-query]').click();
        cy.wait('@chordRecords');
        cy.get('[data-ranking-key=flag-chord-b-v1]').should('be.visible');
        cy.get('[data-cy=minigame-player-id] input').clear();
        cy.get('[data-cy=minigame-player-id] input').type('43');
        cy.get('[data-cy=minigame-records]').should('not.exist');
    });

    it('preserves the loaded record if deletion is rejected', () => {
        cy.intercept('DELETE', `/api/minigame/admin/${firstKey}/player/42`, { statusCode: 403, body: '' }).as('delete');
        loadRecords();
        cy.get(`[data-ranking-key=${firstKey}] [data-cy=minigame-delete]`).click();
        cy.get('.el-message-box__btns button').last().click();
        cy.wait('@delete');
        cy.get(`[data-ranking-key=${firstKey}] [data-cy=minigame-delete]`).should('not.be.disabled');
        cy.get('[data-cy=minigame-records] tbody tr').should('have.length', 2);
        cy.closeElNotifications();
    });
});
