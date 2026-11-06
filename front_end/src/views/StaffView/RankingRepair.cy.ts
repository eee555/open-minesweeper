import RankingRepair from './RankingRepair.vue';

import $axios from '@/http';
import i18n from '@/i18n';

describe('<RankingRepair /> efficiency rankings', () => {
    it('selects the efficiency ranking and repairs sum or an individual level', () => {
        const record = { player_id: 42, b: { value: 1.25, video_id: 8001, upload_time: '2026-10-19T12:00:00Z' }, i: null, e: null, e_nf: { value: 1, video_ids: [8003, 8004, 8005] } };
        cy.intercept('POST', '/api/effranking/thrp/admin/rebuild_record', record).as('repair');
        cy.mount(RankingRepair, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('select[aria-label="Ranking"]').select('thrp');
        cy.get('.ranking-repair .el-input-number input').type('42');
        cy.get('select[aria-label="Statistic"] option').should('have.length', 5);
        cy.get('select[aria-label="Statistic"]').select('sum');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@repair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'sum' });
        });
        cy.get('output').should('contain.text', 'Sum 1.250').and('not.contain.text', 'video ID');
        cy.closeElNotifications();
        cy.get('select[aria-label="Statistic"]').select('b');
        cy.get('output').should('not.exist');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@repair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'b' });
        });
        cy.get('output').should('contain.text', 'Beginner 1.250').and('contain.text', 'video ID 8001');
        cy.closeElNotifications();
        cy.get('select[aria-label="Statistic"]').select('e_nf');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@repair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'e_nf' });
        });
        cy.get('output').should('contain.text', 'Expert NF 1 x 3').and('contain.text', 'video ID 8003');
        cy.closeElNotifications();
        cy.intercept('POST', '/api/effranking/nf_ioe/admin/rebuild_record', {
            player_id: 42, b: { value: 1, video_id: 9001, timems: 500 }, i: null, e: null,
        }).as('ioeRepair');
        cy.get('select[aria-label="Ranking"]').select('nf_ioe');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@ioeRepair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'b' });
        });
        cy.get('output').should('contain.text', 'Beginner 1.000 (0.500)').and('contain.text', 'video ID 9001');
    });

    it('repairs a strict NG ranking through its own endpoint', () => {
        const record = {
            player_id: 42,
            bt: 1234,
            bb: 4.567,
            it: null,
            ib: null,
            et: null,
            eb: null,
            sumt: 2001232,
            sumb: 4.567,
            bt_id: 8001,
            bb_id: 8002,
            it_id: null,
            ib_id: null,
            et_id: null,
            eb_id: null,
        };
        cy.intercept('POST', '/api/speedranking/strict_ng/admin/rebuild_record', record).as('strictNgRepair');
        cy.mount(RankingRepair, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('select[aria-label="Ranking"]').select('strict_ng_nf');
        cy.get('select[aria-label="Statistic"] option').should('have.length', 8);
        cy.get('select[aria-label="Statistic"]').select('sumb');
        cy.get('.ranking-repair .el-input-number input').type('42');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@strictNgRepair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', ranking_name: 'strict_ng_nf', stat: 'sumb' });
        });
        cy.get('output').should('contain.text', '3BV/s Sum 4.567').and('not.contain.text', 'video ID');
        cy.closeElNotifications();
    });
});
