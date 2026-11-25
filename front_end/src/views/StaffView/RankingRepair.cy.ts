import RankingRepair from './RankingRepair.vue';

import $axios from '@/http';
import i18n from '@/i18n';

describe('<RankingRepair /> efficiency rankings', () => {
    beforeEach(() => {
        cy.closeElNotifications();
    });

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
        cy.closeElNotifications();
        cy.intercept('POST', '/api/effranking/tpe/admin/rebuild_record', {
            player_id: 42, i: null, i2: null, i3: { value: 0, video_id: 9002 }, e: null, e2: null, e3: null,
        }).as('tpeRepair');
        cy.get('select[aria-label="Ranking"]').select('tpe');
        cy.get('select[aria-label="Statistic"] option').should('have.length', 9);
        cy.get('select[aria-label="Statistic"]').select('i3');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@tpeRepair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'i3' });
        });
        cy.get('output').should('contain.text', 'Intermediate TPE3 0.000').and('contain.text', 'video ID 9002');
    });

    it('repairs a Path record through its own endpoint', () => {
        const record = {
            player_id: 42,
            b_path: { value: 20, video_id: 8001 },
            i_path: null,
            e_path: null,
            b_cpath: { value: 8, video_id: 8002 },
            i_cpath: { value: 4, video_id: 8003 },
            e_cpath: { value: 2, video_id: 8004 },
            b_epath: { value: 8, video_id: 8005 },
            i_epath: { value: 4, video_id: 8006 },
            e_epath: { value: 2, video_id: 8007 },
        };
        cy.intercept('POST', '/api/effranking/path/admin/rebuild_record', record).as('pathRepair');
        cy.mount(RankingRepair, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('select[aria-label="Ranking"]').select('path');
        cy.get('.ranking-repair .el-input-number input').type('42');
        cy.get('select[aria-label="Statistic"] option').should('have.length', 12);
        cy.get('select[aria-label="Statistic"]').select('sum_epath');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@pathRepair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'sum_epath' });
        });
        // TODO: sum_epath is labeled "Sum EPath", not "Expert EPath"; align this expectation.
        cy.get('output').should('contain.text', 'Expert EPath 0.875').and('not.contain.text', 'video ID');
        cy.closeElNotifications();
        cy.get('select[aria-label="Statistic"]').select('b_cpath');
        cy.get('output').should('not.exist');
        cy.get('.ranking-repair button[type=submit]').click();
        cy.wait('@pathRepair').its('request.body').should((body: string) => {
            expect(Object.fromEntries(new URLSearchParams(body))).to.deep.equal({ player_id: '42', stat: 'b_cpath' });
        });
        cy.get('output').should('contain.text', 'Beginner CPath 0.500').and('contain.text', 'video ID 8002');
        cy.closeElNotifications();
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
