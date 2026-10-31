import tinycolor from 'tinycolor2';

import ThrpCard from './ThrpCard.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { invalidateProfileData } from '@/services/profileDataService';
import type { ThrpPlayerRecord } from '@/services/thrpRankingService';
import { colorTheme } from '@/store';
import { colorThemes } from '@/store/color';
import { pinia } from '@/store/create';
import { local } from '@/store/local';

const record: ThrpPlayerRecord = {
    player_id: 42,
    b: { value: 1.5, video_id: 8001, upload_time: '2026-10-19T12:00:00Z' },
    i: null,
    e: { value: 0.9, video_id: 8002, upload_time: '2026-10-19T12:01:00Z' },
    e_nf: { value: 1, video_ids: [8003, 8004, 8005] },
    ranks: { b: 2, i: null, e: 4, sum: 3, e_nf: 5 },
};
const mountOptions = {
    props: { userId: 42 },
    global: { plugins: [i18n, pinia], config: { globalProperties: { $axios } } },
};

describe('<ThrpCard />', () => {
    const originalColored = local.value.colored;
    const originalIoe = colorTheme.value.ioe;

    beforeEach(() => {
        invalidateProfileData(42);
        invalidateProfileData(43);
        local.value.colored = true;
        colorTheme.value.ioe = { thresholds: [1], colors: ['#224466', '#ffee00'] };
    });
    afterEach(() => {
        local.value.colored = originalColored;
        colorTheme.value.ioe = originalIoe;
    });

    it('renders scores and ranks, links individual videos and colors sum by sum/3', () => {
        cy.intercept('GET', '/api/effranking/thrp/player/42', record).as('records');
        cy.mount(ThrpCard, mountOptions);
        cy.wait('@records');
        cy.get('.thrp-record-table').extractTableData().should('deep.equal', [
            ['Beginner', 'Intermediate', 'Expert', 'Sum', 'Expert NF'],
            ['1.500(2)', '--(--)', '0.900(4)', '2.400(3)', '1 x 3(5)'],
        ]);
        cy.get('.thrp-record-table .video-preview-link').should('have.length', 2).and(($links) => {
            expect([...$links].map((link) => link.getAttribute('href'))).to.deep.equal(['#/video/8001', '#/video/8002']);
        });
        cy.get('[data-field=e_nf] summary').click();
        cy.get('[data-field=e_nf] .video-preview-link').should('have.length', 3).and(($links) => {
            expect([...$links].map((link) => link.getAttribute('href'))).to.deep.equal(['#/video/8003', '#/video/8004', '#/video/8005']);
        });
        cy.get('[data-field=e_nf] summary').click();
        cy.get('[data-field=e_nf] .video-preview-link').should('not.exist');
        cy.get('[data-field=sum] a').should('not.exist');
        cy.get('[data-field=b]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(1.5)).toRgbString());
        cy.get('[data-field=sum]').should('have.css', 'background-color', tinycolor(colorThemes.ioe.value.getColor(0.8)).toRgbString());
        cy.then(() => {
            local.value.colored = false;
        });
        cy.get('[data-field=sum]').should(($cell) => {
            expect($cell[0].style.backgroundColor).to.equal('');
        });
        cy.intercept('GET', '/api/effranking/thrp/player/43', {
            player_id: 43, b: null, i: null, e: null, e_nf: null, ranks: { b: null, i: null, e: null, sum: null, e_nf: null },
        }).as('empty');
        cy.get<ComponentWrapper<typeof ThrpCard>>('@vue').then((wrapper) => wrapper.setProps({ userId: 43 }));
        cy.wait('@empty');
        cy.get('.thrp-record-table tbody').extractTableData().should('deep.equal', [['--(--)', '--(--)', '--(--)', '0.000(--)', '--(--)']]);
        cy.get('.thrp-record-table .video-preview-link').should('not.exist');
        cy.get('@records.all').should('have.length', 1);
    });

    it('retries a failed request and reloads when profile data is invalidated', () => {
        cy.intercept('GET', '/api/effranking/thrp/player/42', { statusCode: 500 }).as('failed');
        cy.mount(ThrpCard, mountOptions);
        cy.wait('@failed');
        cy.get('[role=alert]').should('contain.text', 'Unable to load Thrp records');
        cy.intercept('GET', '/api/effranking/thrp/player/42', record).as('retry');
        cy.get('[role=alert] button').click();
        cy.wait('@retry');
        cy.get('[role=alert]').should('not.exist');
        cy.get('[data-field=b]').should('have.text', '1.500(2)');
        cy.intercept('GET', '/api/effranking/thrp/player/42', { ...record, b: { ...record.b, value: 2 }, e_nf: { value: 1, video_ids: [8003] } }).as('updated');
        cy.then(() => {
            invalidateProfileData(42);
        });
        cy.wait('@updated');
        cy.get('[data-field=b]').should('have.text', '2.000(2)');
        cy.get('[data-field=e_nf] details').should('not.exist');
        cy.get('[data-field=e_nf] .video-preview-link').should('have.attr', 'href', '#/video/8003').and('have.text', '1.000(5)');
    });
});
