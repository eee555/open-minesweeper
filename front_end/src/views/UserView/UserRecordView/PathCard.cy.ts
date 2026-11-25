import PathCard from './PathCard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pathStats } from '@/services/pathRankingService';
import { invalidateProfileData } from '@/services/profileDataService';
import { pinia } from '@/store/create';
import { mockVideoInfo } from '@cy/support/videoInfo';

describe('<PathCard />', () => {
    it('shows all twelve values and ranks, independent missing metrics, and refreshes on invalidation', () => {
        invalidateProfileData(42);
        mockVideoInfo([8001, 8002, 8003, 8004].map((id) => ({ id, software: 'e' })));
        const record = {
            player_id: 42,
            b_path: { value: 0, video_id: 8001 },
            b_cpath: null,
            b_epath: null,
            i_path: { value: 10, video_id: 8002 },
            i_cpath: null,
            i_epath: null,
            e_path: { value: 12.34567, video_id: 8003 },
            e_cpath: null,
            e_epath: null,
            ranks: Object.fromEntries(pathStats.map((stat) => [stat, stat.endsWith('_path') ? 2 : null])),
        };
        cy.intercept('GET', '**/api/effranking/path/player/42', record).as('records');
        cy.mount(PathCard, { props: { userId: 42 }, global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } } });
        cy.wait('@records');
        cy.get('.path-record-table tbody').extractTableData().should('deep.equal', [['0.000(2)', '--(--)', '--(--)', '10.000(2)', '--(--)', '--(--)', '12.346(2)', '--(--)', '--(--)', '22.346(2)', '--(--)', '--(--)']]);
        cy.get('[data-field=e_path]').should('have.attr', 'title', '12.34567');
        cy.get('[data-field=sum_path] a').should('not.exist');
        cy.intercept('GET', '**/api/effranking/path/player/42', { ...record, b_cpath: { value: 0, video_id: 8004 }, ranks: { ...record.ranks, b_cpath: 1 } }).as('updated');
        cy.then(() => {
            invalidateProfileData(42);
        });
        cy.wait('@updated');
        cy.get('[data-field=b_cpath]').should('have.text', '0.000(1)');
    });
});
