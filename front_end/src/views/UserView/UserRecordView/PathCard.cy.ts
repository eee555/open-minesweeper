import tinycolor from 'tinycolor2';

import PathCard from './PathCard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { NFIOEPlayerRecord } from '@/services/nfIOERankingService';
import { pathStats } from '@/services/pathRankingService';
import { invalidateProfileData } from '@/services/profileDataService';
import type { ThrpPlayerRecord } from '@/services/thrpRankingService';
import type { TPEPlayerRecord } from '@/services/tpeRankingService';
import { colorTheme } from '@/store';
import { colorThemes } from '@/store/color';
import { pinia } from '@/store/create';
import { local } from '@/store/local';
import { mockVideoInfo } from '@cy/support/videoInfo';

const mountOptions = { props: { userId: 42 }, global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } } };
const pathRecord = {
    player_id: 42,
    b_path: { value: 0, video_id: 8001 },
    b_cpath: null,
    b_epath: null,
    i_path: { value: 160, video_id: 8002 },
    i_cpath: null,
    i_epath: null,
    e_path: { value: 197.53072, video_id: 8003 },
    e_cpath: null,
    e_epath: null,
    ranks: Object.fromEntries(pathStats.map((stat) => [stat, stat.endsWith('_path') ? 2 : null])),
};
const thrpRecord: ThrpPlayerRecord = {
    player_id: 42,
    b: { value: 1.5, video_id: 8001, upload_time: '2026-10-19T12:00:00Z' },
    i: null,
    e: { value: 0.9, video_id: 8002, upload_time: '2026-10-19T12:01:00Z' },
    e_nf: null,
    ranks: { b: 2, i: null, e: 4, sum: 3, e_nf: null },
};
const tpeRecord: TPEPlayerRecord = {
    player_id: 42,
    i: { value: 0, video_id: 8001 },
    i2: { value: 1, video_id: 8003 },
    i3: { value: 2, video_id: 8004 },
    e: null,
    e2: null,
    e3: null,
    ranks: { i: 2, i2: 3, i3: 4, e: null, e2: null, e3: null, sum: null, sum2: null, sum3: null },
};
const nfIOERecord: NFIOEPlayerRecord = {
    player_id: 42,
    b: { value: 1, video_id: 8005, timems: 34567 },
    i: null,
    e: { value: 0.8, video_id: 8006, timems: 80000 },
    ranks: { b: 1, i: null, e: 2, sum: 3 },
};

describe('<PathCard /> efficiency records', () => {
    const originalColored = local.value.colored;
    const originalIoe = colorTheme.value.ioe;

    beforeEach(() => {
        invalidateProfileData(42);
        local.value.colored = true;
        colorTheme.value.ioe = { thresholds: [1], colors: ['#224466', '#ffee00'] };
        mockVideoInfo([8001, 8002, 8003, 8004, 8005, 8006].map((id) => ({ id, software: 'e' })));
        cy.intercept('GET', '**/api/effranking/path/player/42', pathRecord).as('path');
        cy.intercept('GET', '**/api/effranking/thrp/player/42', thrpRecord).as('thrp');
        cy.intercept('GET', '**/api/effranking/tpe/player/42', tpeRecord).as('tpe');
        cy.intercept('GET', '**/api/effranking/nf_ioe/player/42', nfIOERecord).as('nfIOE');
    });
    afterEach(() => {
        local.value.colored = originalColored;
        colorTheme.value.ioe = originalIoe;
    });

    it('renders all metric rows with links, ranks and colors, then refreshes all records on invalidation', () => {
        cy.mount(PathCard, mountOptions);
        cy.wait(['@path', '@thrp', '@tpe', '@nfIOE']);
        cy.get('.path-record-table').extractTableData().should('deep.equal', [
            ['Efficiency', 'Beginner', 'Intermediate', 'Expert', 'Sum'],
            ['ThrP', '1.500(2)', '--(--)', '0.900(4)', '2.400(3)'],
            ['NF IOE', '1.000(1)', '--(--)', '0.800(2)', '1.800(3)'],
            ['TPE', '', '0.000(2)', '--(--)', '--(--)'],
            ['TPE2', '', '1.000(3)', '--(--)', '--(--)'],
            ['TPE3', '', '2.000(4)', '--(--)', '--(--)'],
            ['Path', '0.000(2)', '10.000(2)', '12.346(2)', '22.346(2)'],
            ['CPath', '--(--)', '--(--)', '--(--)', '--(--)'],
            ['EPath', '--(--)', '--(--)', '--(--)', '--(--)'],
        ]);
        cy.get('[data-field=e_path]').should('have.attr', 'title', '12.34567');
        cy.get('[data-field=sum_path] a').should('not.exist');
        cy.get('[data-field=thrp_b] a').should('have.attr', 'href', '#/video/8001');
        cy.get('[data-field=thrp_b]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(1.5)).toRgbString());
        cy.get('[data-field=thrp_sum]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(0.8)).toRgbString());
        cy.get('[data-field=tpe_i]').should('have.css', 'background-color', tinycolor(colorThemes.itime.value.getColor(0)).toRgbString());
        cy.get('[data-field=nf_ioe_b] a').should('have.attr', 'href', '#/video/8005');
        cy.get('[data-field=nf_ioe_sum]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(0.6)).toRgbString());
        cy.intercept('GET', '**/api/effranking/path/player/42', { ...pathRecord, b_cpath: { value: 0, video_id: 8004 }, ranks: { ...pathRecord.ranks, b_cpath: 1 } }).as('updatedPath');
        cy.intercept('GET', '**/api/effranking/tpe/player/42', {
            ...tpeRecord,
            e: { value: 12.34567, video_id: 8002 },
            e2: { value: 20, video_id: 8005 },
            e3: { value: 30, video_id: 8006 },
            ranks: { ...tpeRecord.ranks, e: 3, e2: 4, e3: 5, sum: 1, sum2: 2, sum3: 3 },
        }).as('updatedTPE');
        cy.intercept('GET', '**/api/effranking/nf_ioe/player/42', {
            ...nfIOERecord,
            i: { value: 1, video_id: 8004, timems: 12000 },
            e: { ...nfIOERecord.e, value: 1 },
            ranks: { ...nfIOERecord.ranks, i: 5, sum: 1 },
        }).as('updatedNFIOE');
        cy.then(() => {
            invalidateProfileData(42);
        });
        cy.wait(['@updatedPath', '@updatedTPE', '@thrp', '@updatedNFIOE']);
        cy.get('.path-record-table tbody').extractTableData().should((rows) => {
            expect(rows[6]?.[1]).to.equal('0.000(1)');
            expect(rows[1]).to.deep.equal(['NF IOE', '1.000(1)', '1.000(5)', '1.000(2)', '3.000(1)']);
            expect(rows.slice(2, 5)).to.deep.equal([
                ['TPE', '', '0.000(2)', '12.346(3)', '12.346(1)'],
                ['TPE2', '', '1.000(3)', '20.000(4)', '21.000(2)'],
                ['TPE3', '', '2.000(4)', '30.000(5)', '32.000(3)'],
            ]);
        });
        cy.get('[data-field=tpe_e]').should('have.attr', 'title', '12.34567');
        cy.get('[data-field=tpe_e3] a').should('have.attr', 'href', '#/video/8006');
        cy.get('[data-field=tpe_sum3] a').should('not.exist');
        cy.get('[data-field=tpe_sum3]').should(($cell) => {
            expect($cell[0].style.backgroundColor).to.equal('');
        });
        cy.then(() => {
            local.value.colored = false;
        });
        cy.get('[data-field=thrp_sum], [data-field=tpe_i], [data-field=nf_ioe_sum]').should(($cells) => {
            expect([...$cells].every((cell) => cell.style.backgroundColor === '')).to.equal(true);
        });
    });

    it('keeps successful records visible when another request fails and retries only the failed request', () => {
        cy.intercept('GET', '**/api/effranking/path/player/42', { statusCode: 500 }).as('failed');
        cy.mount(PathCard, mountOptions);
        cy.wait(['@failed', '@thrp', '@tpe', '@nfIOE']);
        cy.get('[role=alert]').should('contain.text', 'Unable to load some efficiency records');
        cy.get('.path-record-table tbody').extractTableData().should((rows) => {
            expect(rows[0]?.[1]).to.equal('1.500(2)');
            expect(rows[5]?.[1]).to.equal('--(--)');
            expect(rows[2]?.[2]).to.equal('0.000(2)');
        });
        cy.intercept('GET', '**/api/effranking/path/player/42', pathRecord).as('retry');
        cy.get('[role=alert] button').click();
        cy.wait('@retry');
        cy.get('[role=alert]').should('not.exist');
        cy.get('.path-record-table tbody').extractTableData().should((rows) => {
            expect(rows[5]?.[1]).to.equal('0.000(2)');
        });
        cy.get('@thrp.all').should('have.length', 1);
        cy.get('@tpe.all').should('have.length', 1);
        cy.get('@nfIOE.all').should('have.length', 1);
    });
});
