import StrictNgCard from './StrictNgCard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { invalidateProfileData } from '@/services/profileDataService';
import type { StrictNgPlayerRecord } from '@/services/strictNgRankingService';
import { colorTheme } from '@/store';
import { pinia } from '@/store/create';
import { local } from '@/store/local';

const mountOptions = {
    props: { userId: 42 },
    global: {
        plugins: [i18n, pinia],
        config: {
            globalProperties: {
                $axios,
            },
        },
    },
};

describe('<StrictNgCard />', () => {
    const originalColored = local.value.colored;
    const originalBtime = colorTheme.value.btime;
    const originalBvs = colorTheme.value.bvs;

    beforeEach(() => {
        local.value.colored = true;
        colorTheme.value.btime = { thresholds: [2], colors: ['#224466', '#ffee00'] };
        colorTheme.value.bvs = { thresholds: [1], colors: ['#405060', '#abcdef'] };
        const record: StrictNgPlayerRecord = {
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
            ranks: { bt: 2, bb: 3, it: null, ib: null, et: null, eb: null, sumt: 4, sumb: 5 },
        };
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/strict_ng/player/42' }, {
            body: {
                strict_ng: record,
                strict_ng_nf: { ...record, bt: 2345, bb: 0, sumt: 2002343, sumb: 0, ranks: { ...record.ranks, bt: 6, bb: null, sumt: 7, sumb: 8 } },
            },
        }).as('strictNgRecords');
        cy.then(() => {
            invalidateProfileData(42);
            invalidateProfileData(43);
        });
    });

    afterEach(() => {
        local.value.colored = originalColored;
        colorTheme.value.btime = originalBtime;
        colorTheme.value.bvs = originalBvs;
    });

    it('loads both speed rankings once and renders scores with ranks', () => {
        cy.mount(StrictNgCard, mountOptions);

        cy.wait('@strictNgRecords').its('request.query').should('deep.equal', {});

        cy.get('.strict-ng-record-table').extractTableData().should('deep.equal', [
            ['Strict NG', 'Beginner', 'Intermediate', 'Expert', 'Sum'],
            ['Time', '1.234(2)', '--(--)', '--(--)', '2001.232(4)'],
            ['Bvs', '4.567(3)', '--(--)', '--(--)', '4.567(5)'],
            ['Time (NF)', '2.345(6)', '--(--)', '--(--)', '2002.343(7)'],
            ['Bvs (NF)', '0.000(--)', '--(--)', '--(--)', '0.000(8)'],
        ]);
        cy.get('.strict-ng-record-table .video-preview-link').should('have.length', 4).and(($links) => {
            expect([...$links].map((link) => link.getAttribute('href'))).to.deep.eq(['#/video/8001', '#/video/8002', '#/video/8001', '#/video/8002']);
        });
        cy.get('@strictNgRecords.all').should('have.length', 1);
        cy.get('.strict-ng-record-table tbody tr td:first-of-type').should(($cells) => {
            expect([...$cells].map((cell) => getComputedStyle(cell).backgroundColor)).to.deep.equal([
                'rgb(34, 68, 102)', 'rgb(171, 205, 239)', 'rgb(255, 238, 0)', 'rgb(64, 80, 96)',
            ]);
        });
        cy.get('.strict-ng-record-table tbody tr td:not(:first-of-type)').should(($cells) => {
            expect([...$cells].every((cell) => cell.style.backgroundColor === '')).to.equal(true);
        });
        cy.then(() => {
            local.value.colored = false;
        });
        cy.get('.strict-ng-record-table tbody td').should(($cells) => {
            expect([...$cells].every((cell) => cell.style.backgroundColor === '')).to.equal(true);
        });
    });

    it('reloads for another user and keeps all four rows without records', () => {
        cy.mount(StrictNgCard, mountOptions);
        cy.wait('@strictNgRecords');
        cy.get('.strict-ng-record-table').contains('1.234(2)').should('be.visible');
        const empty: StrictNgPlayerRecord = {
            player_id: 43,
            bt: null,
            bb: null,
            it: null,
            ib: null,
            et: null,
            eb: null,
            sumt: 2999997,
            sumb: 0,
            bt_id: null,
            bb_id: null,
            it_id: null,
            ib_id: null,
            et_id: null,
            eb_id: null,
            ranks: { bt: null, bb: null, it: null, ib: null, et: null, eb: null, sumt: null, sumb: null },
        };
        cy.intercept({ method: 'GET', pathname: '/api/speedranking/strict_ng/player/43' }, {
            body: { strict_ng: empty, strict_ng_nf: empty },
        }).as('emptyRecords');
        cy.get<ComponentWrapper<typeof StrictNgCard>>('@vue').then((wrapper) => wrapper.setProps({ userId: 43 }));
        cy.wait('@emptyRecords');
        cy.get('.strict-ng-record-table tbody').extractTableData().should('deep.equal', [
            ['Time', '--(--)', '--(--)', '--(--)', '2999.997(--)'],
            ['Bvs', '--(--)', '--(--)', '--(--)', '0.000(--)'],
            ['Time (NF)', '--(--)', '--(--)', '--(--)', '2999.997(--)'],
            ['Bvs (NF)', '--(--)', '--(--)', '--(--)', '0.000(--)'],
        ]);
        cy.get('.strict-ng-record-table .video-preview-link').should('not.exist');
    });
});
