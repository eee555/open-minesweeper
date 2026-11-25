import App from './App.vue';
import PathCard from './PathCard.vue';
import SaoleiCard from './SaoleiCard.vue';
import ThrpCard from './ThrpCard.vue';
import TPECard from './TPECard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { store } from '@/store';
import { pinia } from '@/store/create';
import { UserProfile } from '@/utils/userprofile';

describe('<UserRecordViewApp />', () => {
    it('passes the user id to ranking cards and loads a complete pluck record table', () => {
        store.$reset();
        store.player = new UserProfile({ id: 42, realname: 'Test Player' });
        cy.intercept({ method: 'GET', pathname: '/api/customranking/pluck/player' }, {
            body: [
                { level: 'c8_8_40', video_id: 9001, pluck: 0.123456 },
                { level: 'c16_30_150', video_id: 9002, pluck: 0.987654 },
            ],
        }).as('pluckRecords');
        cy.mount(App, {
            global: {
                plugins: [i18n, pinia],
                config: { globalProperties: { $axios } },
                stubs: { SaoleiCard: true, ThrpCard: true, TPECard: true, PathCard: true },
            },
        }).then(({ wrapper }) => {
            expect(wrapper.findComponent(SaoleiCard).props('userId')).to.equal(42);
            expect(wrapper.findComponent(ThrpCard).props('userId')).to.equal(42);
            expect(wrapper.findComponent(TPECard).props('userId')).to.equal(42);
            expect(wrapper.findComponent(PathCard).props('userId')).to.equal(42);
        });

        cy.wait('@pluckRecords').its('request.query').should('deep.equal', { player_id: '42' });
        cy.get('.pluck-record-table tbody').extractTableData().should('deep.equal', [
            ['8x8/40', '0.123456'],
            ['16x16/100', '--'],
            ['16x30/150', '0.987654'],
            ['24x30/200', '--'],
        ]);
        cy.get('.pluck-record-table .video-preview-link').should('have.length', 2).and(($links) => {
            expect([...$links].map((link) => link.getAttribute('href'))).to.deep.eq(['#/video/9001', '#/video/9002']);
        });
    });
});
