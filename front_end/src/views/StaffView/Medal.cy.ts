import Medal from './Medal.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { StaffMedalDefinition, StaffPlayerMedals } from '@/services/staffMedalService';
import { store } from '@/store';
import { MedalDirection, MedalKind, MedalSeries } from '@/utils/medal_const';

const definition: StaffMedalDefinition = {
    code: 'time.b',
    series: MedalSeries.BREAKTHROUGH,
    subseries: '',
    kind: MedalKind.PB,
    metric: 'time',
    direction: MedalDirection.DESC,
    level: 'b',
    style: '',
    thresholds: [10_000, 20_000],
    active: true,
    hidden: false,
};

function player(id = 42): StaffPlayerMedals {
    return { user_id: id, username: `Player ${id}`, grants: [], overrides: [], history: [] };
}

function mountMedals() {
    cy.mount(Medal, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
}

function loadPlayer(id = 42) {
    cy.get('.player-form input').clear();
    cy.get('.player-form input').type(String(id));
    cy.get('.player-form button[type=submit]').click();
    cy.get('.player-label').should('contain', `Player ${id}`);
}

function selectOption(index: number, label: string) {
    cy.get('.override-form .el-select').eq(index).click();
    cy.get('.el-select-dropdown__item').filter(':visible').contains(label).click();
}

describe('staff medal management', () => {
    beforeEach(() => {
        store.user.is_staff = true;
        cy.intercept('GET', '/api/medal/staff/catalog', [definition]).as('catalog');
        cy.intercept('GET', '/api/medal/staff/players/42', player()).as('player');
    });
    afterEach(() => {
        store.user.is_staff = false;
    });

    it('requires a stage, award date and reason before forcing a grant', () => {
        cy.intercept('POST', '/api/medal/staff/overrides', { grant_id: 1, mode: 'grant', enqueued: false }).as('save');
        mountMedals();
        loadPlayer();
        selectOption(0, 'time.b');
        cy.get('.override-form input[aria-label="Edition / scope key (optional)"]').should('be.disabled');
        cy.get('.override-form').should('contain', 'Locks the selected stage');
        cy.get('.override-form button[type=submit]').should('be.disabled');
        selectOption(2, '(10000)');
        cy.get('input[type=date]').type('2026-10-23');
        cy.get('.override-form textarea').type('Reviewed manual award');
        cy.get('.override-form button[type=submit]').should('be.enabled').click();
        cy.wait('@save').its('request.body').should((body: string) => {
            expect(JSON.parse(body)).to.deep.equal({
                user_id: 42,
                code: 'time.b',
                scope_key: '',
                mode: 'grant',
                stage: 10_000,
                granted_on: '2026-10-23',
                reason: 'Reviewed manual award',
            });
        });
        cy.get('output').should('contain', 'Manual decision saved');
        cy.get('.override-form textarea').should('have.value', '');
    });

    it('blocks an unearned medal for a particular scope without a date or stage', () => {
        cy.intercept('GET', '/api/medal/staff/catalog', [{ ...definition, kind: MedalKind.MANUAL }]);
        cy.intercept('POST', '/api/medal/staff/overrides', { grant_id: null, mode: 'revoke', enqueued: false }).as('save');
        mountMedals();
        loadPlayer();
        selectOption(0, 'time.b');
        selectOption(1, 'Revoke / block grants');
        cy.get('.override-form input[aria-label="Edition / scope key (optional)"]').type('2026-autumn');
        cy.get('.override-form textarea').type('Disqualified for this edition');
        cy.get('input[type=date]').should('not.exist');
        cy.get('.override-form button[type=submit]').click();
        cy.wait('@save').its('request.body').should((body: string) => {
            expect(JSON.parse(body)).to.deep.equal({ user_id: 42, code: 'time.b', scope_key: '2026-autumn', mode: 'revoke', reason: 'Disqualified for this edition' });
        });
    });

    it('offers stage 1 for a manual definition with no thresholds', () => {
        cy.intercept('GET', '/api/medal/staff/catalog', [{ ...definition, code: 'manual.award', series: 'Manual award', kind: MedalKind.MANUAL, thresholds: [] }]);
        mountMedals();
        loadPlayer();
        selectOption(0, 'manual.award');
        selectOption(2, '1');
        cy.get('input[type=date]').type('2026-10-23');
        cy.get('.override-form textarea').type('Manual award at its default stage');
        cy.get('.override-form button[type=submit]').should('be.enabled');
    });

    it('restores a deleted definition override in its exact scope and explains background recalculation', () => {
        const data = player();
        data.overrides = [{ id: 1, definition_code: 'deleted.medal', scope_key: '2026-autumn', mode: 'grant', stage: 10, reason: 'Old award', actor_id: 7, updated_at: '2026-10-23' }];
        cy.intercept('GET', '/api/medal/staff/players/42', data);
        cy.intercept('POST', '/api/medal/staff/overrides', { grant_id: null, mode: 'auto', enqueued: true }).as('save');
        mountMedals();
        loadPlayer();
        cy.get('[data-cy=overrides]').should('contain', 'Definition deleted');
        cy.get('[data-cy=overrides] button').click();
        cy.get('.override-form').should('contain', 'background task');
        cy.get('.override-form button[type=submit]').should('be.disabled');
        cy.get('.override-form textarea').type('Use actual progress');
        cy.get('.override-form button[type=submit]').click();
        cy.wait('@save').its('request.body').should((body: string) => {
            expect(JSON.parse(body)).to.deep.equal({ user_id: 42, code: 'deleted.medal', scope_key: '2026-autumn', mode: 'auto', reason: 'Use actual progress' });
        });
        cy.get('output').should('contain', 'waiting for the background task');
    });

    it('does not offer restoration for a naturally earned medal without an override', () => {
        mountMedals();
        loadPlayer();
        selectOption(0, 'time.b');
        cy.get('.override-form .el-select').eq(1).click();
        cy.contains('.el-select-dropdown__item:visible', 'Restore automatic').should('have.class', 'is-disabled');
    });

    for (const failed of [false, true]) {
        it(`ignores the previous player's late ${failed ? 'failure' : 'success'}`, () => {
            let release!: () => void;
            const pending = new Promise<void>((resolve) => {
                release = resolve;
            });
            cy.intercept('GET', '/api/medal/staff/players/42', async (request) => {
                await pending;
                request.reply(failed ? { statusCode: 500, body: {} } : { body: player() });
            }).as('old');
            cy.intercept('GET', '/api/medal/staff/players/43', player(43));
            mountMedals();
            cy.get('.player-form input').type('42');
            cy.get('.player-form button[type=submit]').click();
            loadPlayer(43);
            cy.then(() => {
                release();
            });
            cy.wait('@old');
            cy.get('.player-label').should('contain', 'Player 43');
            cy.get('[role=alert]').should('not.exist');
        });
    }

    it('makes no staff requests and renders no form for non-staff viewers', () => {
        store.user.is_staff = false;
        const get = cy.stub($axios, 'get');
        mountMedals();
        cy.contains('staff only').should('be.visible');
        cy.get('.staff-medals').should('not.exist');
        cy.then(() => expect(get).not.to.have.been.called);
    });
});
