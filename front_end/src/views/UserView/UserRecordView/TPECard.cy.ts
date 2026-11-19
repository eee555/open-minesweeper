import TPECard from './TPECard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { invalidateProfileData } from '@/services/profileDataService';
import { pinia } from '@/store/create';

describe('<TPECard />', () => {
    it('renders zero, missing sums and ranks, then refreshes on profile invalidation', () => {
        invalidateProfileData(42);
        cy.intercept('GET', '**/api/effranking/tpe/player/42', {
            player_id: 42,
            i: { value: 0, video_id: 8001 },
            i2: { value: 1, video_id: 8003 },
            i3: { value: 2, video_id: 8004 },
            e: null,
            e2: null,
            e3: null,
            ranks: { i: 2, i2: 3, i3: 4, e: null, e2: null, e3: null, sum: null, sum2: null, sum3: null },
        }).as('records');
        cy.mount(TPECard, { props: { userId: 42 }, global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } } });
        cy.wait('@records');
        cy.get('.tpe-record-table th[scope=colgroup]').should('have.length', 3).and('have.attr', 'colspan', '3');
        cy.get('.tpe-record-table tbody').extractTableData().should('deep.equal', [['0.000(2)', '1.000(3)', '2.000(4)', '--(--)', '--(--)', '--(--)', '--(--)', '--(--)', '--(--)']]);
        cy.get('[data-field=i] .video-preview-link').should('have.attr', 'href', '#/video/8001');
        cy.intercept('GET', '**/api/effranking/tpe/player/42', {
            player_id: 42,
            i: { value: 0, video_id: 8001 },
            i2: { value: 1, video_id: 8003 },
            i3: { value: 2, video_id: 8004 },
            e: { value: 12.34567, video_id: 8002 },
            e2: { value: 20, video_id: 8005 },
            e3: { value: 30, video_id: 8006 },
            ranks: { i: 2, i2: 3, i3: 4, e: 3, e2: 4, e3: 5, sum: 1, sum2: 2, sum3: 3 },
        }).as('updated');
        cy.then(() => {
            invalidateProfileData(42);
        });
        cy.wait('@updated');
        cy.get('.tpe-record-table tbody').extractTableData().should('deep.equal', [['0.000(2)', '1.000(3)', '2.000(4)', '12.346(3)', '20.000(4)', '30.000(5)', '12.346(1)', '21.000(2)', '32.000(3)']]);
        cy.get('[data-field=e]').should('have.attr', 'title', '12.34567');
        cy.get('[data-field=sum] a').should('not.exist');
        cy.get('[data-field=e3] .video-preview-link').should('have.attr', 'href', '#/video/8006');
        cy.get('[data-field=sum3] a').should('not.exist');
    });
});
