import PBRecordGrid from './PBRecordGrid.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { PBPlayerRecord } from '@/services/pbRankingService';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const recordsMap = {
    collection: {
        'std:b:count': 2, 'std:b:probability': 0.012345, 'std:b:asb': 1.23456,
    },
    skill: { 'std:b:total': 3.5, 'std:b:s1': 1.23456, 'std:b:s2': 2 },
    typical_time: { 'std:b:total': 3999.996, 'std:b:s1': 12.3456, 'std:b:s2': 999.999 },
};

const ranksMap = {
    collection: { 'std:b:count': 7, 'std:b:probability': 8, 'std:b:asb': 9 },
    skill: { 'std:b:total': 4, 'std:b:s1': 5, 'std:b:s2': 6 },
    typical_time: { 'std:b:total': 10, 'std:b:s1': 11, 'std:b:s2': 12 },
};

const pbRecords: PBPlayerRecord[] = [
    { level: 'b', bv: 1, nf: false, timems: 1000, video_id: 1, rank: 1 },
    { level: 'b', bv: 10, nf: false, timems: 2000, video_id: 2, rank: 2 },
];
const expertRecord: PBPlayerRecord[] = [{ level: 'e', bv: 130, nf: false, timems: 3000, video_id: 3, rank: 1 }];

describe('<PBRecordGrid /> derived summary', () => {
    installHashHistoryCleanup();

    it('shows level totals, segment cells spanning visible rows and raw-value titles', () => {
        const router = hashRouter();
        cy.mount(PBRecordGrid, {
            props: { records: pbRecords, level: 'b', nf: false, stat: 'time', derivedRecords: recordsMap, derivedRanks: ranksMap, colored: true },
            global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } },
        });
        cy.get('.pb-level-title').should('contain.text', '2(7)').and('contain.text', '1.23%(8)').and('contain.text', '1.235(9)').and('contain.text', '3.500(4)').and('contain.text', '3999.996(10)');
        cy.get('.pb-level-title [title="1.23456"]').should('exist');
        cy.get('.pb-side-head').should('have.length', 1);
        cy.get('.pb-side-cell').should('have.length', 2);
        cy.get('[data-cy="pb-side-b-s1-tt"]').should('have.text', '12.346').and('have.attr', 'title', '12.3456');
        cy.get('[data-cy="pb-side-b-s2-tt"]').should('have.text', '999.999').and('have.attr', 'title', '999.999');
        cy.get<ComponentWrapper<typeof PBRecordGrid>>('@vue').then((wrapper) => wrapper.setProps({ stat: 'bvs' }));
        cy.get('[data-cy="pb-side-b-s1-skill"]').should('have.text', '1.235');
        cy.get<ComponentWrapper<typeof PBRecordGrid>>('@vue').then((wrapper) => wrapper.setProps({ stat: 'rank' }));
        cy.get('.pb-side-head').should('have.length', 2);
        cy.get('[data-cy="pb-side-b-s1-skill-rank"]').should('have.text', '5');
        cy.get('[data-cy="pb-side-b-s2-tt-rank"]').should('have.text', '12');
        cy.get<ComponentWrapper<typeof PBRecordGrid>>('@vue').then((wrapper) => wrapper.setProps({ stat: 'stnb' }));
        cy.get('.pb-side-grid').should('not.exist');
    });

    it('renders only the segment intersecting visible rows without adding rows for a long one', () => {
        const router = hashRouter();
        cy.mount(PBRecordGrid, {
            props: {
                records: expertRecord,
                level: 'e',
                nf: false,
                stat: 'time',
                derivedRecords: recordsMap,
                derivedRanks: ranksMap,
                colored: false,
            },
            global: { plugins: [i18n, pinia, router], config: { globalProperties: { $axios } } },
        });
        cy.get('.pb-grid .pb-label').should('have.length', 11);
        cy.get('[data-cy="pb-side-e-s1-tt"]').should('not.exist');
        cy.get('[data-cy="pb-side-e-s2-tt"]').should('have.length', 1);
        cy.get('.pb-side-cell').should('have.length', 1);
    });
});
