import TPECard from './TPECard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { invalidateProfileData } from '@/services/profileDataService';
import { pinia } from '@/store/create';

describe('<TPECard />', () => {
    it('renders zero, missing sums and ranks, then refreshes on profile invalidation', () => {
        invalidateProfileData(42);
        cy.intercept('GET', '**/api/effranking/tpe/player/42', {
            player_id: 42, i: { value: 0, video_id: 8001 }, e: null, ranks: { i: 2, e: null, sum: null },
        }).as('records');
        cy.mount(TPECard, { props: { userId: 42 }, global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } } });
        cy.wait('@records');
        cy.get('.tpe-record-table').extractTableData().should('deep.equal', [
            ['Intermediate', 'Expert', 'Sum'], ['0.000(2)', '--(--)', '--(--)'],
        ]);
        cy.get('[data-field=i] .video-preview-link').should('have.attr', 'href', '#/video/8001');
        cy.intercept('GET', '**/api/effranking/tpe/player/42', {
            player_id: 42, i: { value: 0, video_id: 8001 }, e: { value: 12.34567, video_id: 8002 }, ranks: { i: 2, e: 3, sum: 1 },
        }).as('updated');
        cy.then(() => {
            invalidateProfileData(42);
        });
        cy.wait('@updated');
        cy.get('.tpe-record-table tbody').extractTableData().should('deep.equal', [['0.000(2)', '12.346(3)', '12.346(1)']]);
        cy.get('[data-field=e]').should('have.attr', 'title', '12.34567');
        cy.get('[data-field=sum] a').should('not.exist');
    });
});
