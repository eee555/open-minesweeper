import tinycolor from 'tinycolor2';

import PBRankingTable from './PBRankingTable.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { videoplayerstore } from '@/store';
import { colorThemes } from '@/store/color';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<PBRankingTable />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        cy.mockPlayerNameFallback();
        videoplayerstore.visible = false;
    });

    afterEach(() => {
        videoplayerstore.visible = false;
    });

    it('renders the columns, rank offset, derived metrics and video preview for the supplied records', () => {
        const upload = new Date(2026, 9, 5, 12, 34, 0).toISOString();
        cy.mount(PBRankingTable, {
            props: { rows: [{ player_id: 42, video_id: 8001, timems: 1000, upload_time: upload }], level: 'b', bv: 1, first: 20, loading: false },
            global: { plugins: [i18n, pinia, hashRouter()], config: { globalProperties: { $axios } } },
        });
        cy.get('.pb-ranking-table .video-preview-link').should('not.exist');
        cy.get('.pb-ranking-table thead').extractTableData().should((data) => {
            expect(data[0]).to.deep.equal(['#', 'Player', 'Time', 'Bvs', 'STNB', 'Upload Time']);
        });
        cy.get('.pb-ranking-table tbody').extractTableData().should((data) => {
            expect(data).to.have.length(1);
            expect(data[0]?.[0]).to.equal('21');
            expect(data[0]?.slice(2)).to.deep.equal(['1.000', '1.000', '36.000', '2026-10-05 12:34']);
        });
        cy.get<ComponentWrapper<typeof PBRankingTable>>('@vue').then((wrapper) => wrapper.setProps({ colored: true }));
        for (const [index, theme, value] of [[2, 'btime', 1], [3, 'bvs', 1], [4, 'stnb', 36]] as const) {
            cy.get('.pb-ranking-table tbody td').eq(index).should('have.css', 'background-color', tinycolor(colorThemes[theme].value.getColor(value)).toRgbString());
        }
        cy.get<ComponentWrapper<typeof PBRankingTable>>('@vue').then((wrapper) => wrapper.setProps({ colored: false }));
        cy.get('.pb-ranking-table tbody td').eq(2).should(($cell) => {
            expect($cell[0].style.backgroundColor).to.equal('');
        });
        cy.get('.pb-ranking-table a[href="#/player/42"]').should('exist');
        // Keep the mounted test on this page while checking that player links do not open the preview.
        cy.get('.pb-ranking-table a[href="#/player/42"]').then(($link) => {
            $link[0].addEventListener('click', (event) => {
                event.preventDefault();
            }, { once: true });
        });
        cy.get('.pb-ranking-table a[href="#/player/42"]').click();
        cy.wrap(videoplayerstore).its('visible').should('eq', false);
        cy.get('.pb-ranking-table tbody tr').first().find('td').eq(2).click();
        cy.wrap(videoplayerstore).its('visible').should('eq', true);
        cy.wrap(videoplayerstore).its('id').should('eq', 8001);
        cy.wrap(videoplayerstore).its('url').should('include', '/api/video/preview?id=8001');

        cy.get<ComponentWrapper<typeof PBRankingTable>>('@vue').then((wrapper) => wrapper.setProps({ level: 'e', bv: 2, first: 0 }));
        cy.get('.pb-ranking-table tbody').extractTableData().should((data) => {
            expect(data[0]?.[0]).to.equal('1');
            expect(data[0]?.slice(2, 5)).to.deep.equal(['1.000', '2.000', '870.000']);
        });

        for (const key of ['Enter', 'Space'] as const) {
            cy.then(() => {
                videoplayerstore.visible = false;
            });
            cy.get('.pb-ranking-table tbody tr').first().focus();
            cy.realPress(key);
            cy.wrap(videoplayerstore).its('visible').should('eq', true);
        }
    });

    it('renders the empty and loading states, then displays zero-time metrics as infinity', () => {
        cy.mount(PBRankingTable, {
            props: { rows: [], level: 'b', bv: 1, first: 0, loading: false },
            global: { plugins: [i18n, pinia, hashRouter()], config: { globalProperties: { $axios } } },
        });
        cy.get('.pb-ranking-table .base-table-empty').should('have.text', 'No records').and('have.attr', 'colspan', '6');
        cy.get<ComponentWrapper<typeof PBRankingTable>>('@vue').then((wrapper) => wrapper.setProps({ loading: true }));
        cy.get('.pb-ranking-table .el-loading-mask').should('be.visible');

        cy.get<ComponentWrapper<typeof PBRankingTable>>('@vue').then((wrapper) => wrapper.setProps({
            loading: false,
            rows: [{ player_id: 77, video_id: 8002, timems: 0, upload_time: new Date(2026, 9, 5, 12, 35, 0).toISOString() }],
        }));
        cy.shouldBeAbsentOrHidden('.pb-ranking-table .el-loading-mask');
        cy.get('.pb-ranking-table .base-table-empty').should('not.exist');
        cy.get('.pb-ranking-table tbody').extractTableData().should((data) => {
            expect(data).to.have.length(1);
            expect(data[0]?.slice(2)).to.deep.equal(['0.000', 'Infinity', 'Infinity', '2026-10-05 12:35']);
        });
    });
});
