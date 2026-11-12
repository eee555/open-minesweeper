import SkillTTRanking from './SkillTTRanking.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const records = {
    skill: { 'std:sum:total': 1.23456, 'std:b:s1': 2.5, 'std:b:total': 3.5, 'nf:b:s1': 1.5, 'nf:b:total': 2 },
    typical_time: { 'std:sum:total': 3999.996, 'std:b:s1': 12.3456, 'std:b:total': 3999.996, 'nf:b:s1': 999.999, 'nf:b:total': 3999.996 },
};

describe('<SkillTTRanking />', () => {
    installHashHistoryCleanup();

    it('opens the overview and switches to a level segment page with its own default sort', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/rank' }, {
            body: { count: 3, rows: [{ player_id: 42, records }] },
        }).as('ranking');
        const router = hashRouter({ initialPath: '/ranking/speed/skill_tt' });
        cy.mount(SkillTTRanking, { props: { colored: true }, global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        cy.wait('@ranking').its('request.query').should('include', { ranking: 'skill', field: 'std:sum:total' });
        cy.get('.derived-ranking-table thead th').should('have.length', 12);
        cy.get('.derived-ranking-table thead th[scope="colgroup"][colspan="4"]').should('have.length', 2);
        cy.get('.derived-ranking-table tbody [data-field="skill:sum:total"]').should('have.text', '1.235').and('have.attr', 'title', '1.23456');
        cy.get('[data-cy=derived-view] [data-view=tt_b]').click();
        cy.wait('@ranking').its('request.query').should('include', { ranking: 'typical_time', field: 'std:b:total' });
        cy.get('.derived-ranking-table thead th').should('have.length', 7);
        cy.get('.derived-ranking-table thead th[scope="colgroup"]').should('not.exist');
        cy.get('[data-cy=derived-nf]').check();
        cy.wait('@ranking').its('request.query').should('include', { field: 'nf:b:total' });
        cy.get('.derived-ranking-table tbody [data-field="typical_time:b:s1"]').should('have.text', '999.999');
        cy.wrap(router).its('currentRoute.value.query').should('include', { view: 'tt_b', nf: '1', page: '1' });
    });

    it('restores a shared URL sort on the first request', () => {
        cy.mockPlayerNameFallback();
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/pb_derived/rank' }, {
            body: { count: 1, rows: [{ player_id: 42, records }] },
        }).as('ranking');
        const router = hashRouter({ initialPath: '/ranking/speed/skill_tt?view=tt_b&sort=typical_time:b:s2' });
        cy.wrap(router.isReady()).then(() => {
            cy.mount(SkillTTRanking, { props: { colored: false }, global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } } });
        });
        cy.wait('@ranking').its('request.query').should('include', { ranking: 'typical_time', field: 'std:b:s2' });
        cy.get('.derived-ranking-table thead [aria-sort=ascending] [data-field]').should('have.attr', 'data-field', 'typical_time:b:s2');
        cy.get('@ranking.all').should('have.length', 1);
    });
});
