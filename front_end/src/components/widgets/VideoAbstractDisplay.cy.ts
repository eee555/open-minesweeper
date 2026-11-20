import { defineComponent, h } from 'vue';

import VideoAbstractDisplay from './VideoAbstractDisplay.vue';

import { videoDescriptionStore } from '@/components/VideoList/columnStore';
import { defaultVideoDescription } from '@/components/VideoList/presets';
import i18n from '@/i18n';
import { VideoAbstract } from '@/utils/videoabstract';
import { mockVideoInfo } from '@cy/support/videoInfo';

describe('<VideoAbstractDisplay />', () => {
    beforeEach(() => {
        videoDescriptionStore.columns.value = defaultVideoDescription();
    });
    it('loads missing parsed fields by ID without requesting metadata or inventing an upload date', () => {
        mockVideoInfo([{ id: 42, software: 'a', timems: 12345, bv: 100, cl: 30, ce: 20 }]);
        cy.mount(VideoAbstractDisplay, { props: { id: 42 }, global: { plugins: [i18n] } });
        cy.wait('@parsedVideoInfo').its('request.query.ids').should('eq', '42');
        cy.get('.descriptions').should('contain.text', '12.345').and('contain.text', '100');
        cy.get('.descriptions dd').should('have.length', 11);
        cy.get('@videoMetadata.all').should('have.length', 0);
    });

    it('renders absent data as placeholders and invalid dates as NaN without invented dates', () => {
        cy.mount(VideoAbstractDisplay, { global: { plugins: [i18n] } });
        cy.get('.descriptions dd').should('have.length', 11).and('have.text', '—'.repeat(11));
        cy.get('.descriptions').should('not.contain.text', 'NaN').and('not.contain.text', 'Invalid Date');
        cy.get('img').should('not.exist');
        cy.get<ComponentWrapper<typeof VideoAbstractDisplay>>('@vue').then((wrapper) => wrapper.setProps({
            video: { software: 'a', level: 'e', mode: '00', timems: 12345, bv: 100, upload_time: 'invalid', end_time: new Date(NaN) },
        }));
        cy.get('.descriptions dd').should('have.length', 11);
        cy.get('.descriptions').should('contain.text', '12.345').and('contain.text', '100').and('not.contain.text', 'Invalid Date');
        cy.get('img').should('have.length', 1);
        cy.get<ComponentWrapper<typeof VideoAbstractDisplay>>('@vue').then((wrapper) => wrapper.setProps({ video: null }));
        cy.get('.descriptions dd').should('have.length', 11).and('have.text', '—'.repeat(11));
    });

    it('keeps valid zero statistics and accepts a complete VideoAbstract', () => {
        cy.mount(VideoAbstractDisplay, {
            props: { video: new VideoAbstract({ id: 1, software: 'e', level: 'b', mode: '00', timems: 0, bv: 0, cl: 0, ce: 0, upload_time: '2026-10-22T00:00:00Z', state: 'c' }) },
            global: { plugins: [i18n] },
        });
        cy.get('.descriptions dd').eq(2).should('have.text', '0.000');
        cy.get('.descriptions dd').eq(3).should('have.text', '0');
    });

    it('renders general data, typed booleans and clamps item widths in narrow containers', () => {
        videoDescriptionStore.columns.value = [
            { type: 'data', key: 'time', expr: 'level', width: 3 },
            { type: 'bool', key: 'NF', expr: 'right_ce == 0', width: 1 },
            { type: 'data', key: 'Values', expr: '[bv, timems / 1000]', width: 2 },
        ];
        const video = new VideoAbstract({ id: 1, software: 'a', mode: '00', level: 'c16_30_150', bv: 100, timems: 12345, right_ce: 1 });
        cy.mount(defineComponent({ expose: [], render: () => h('div', { style: 'width: 180px' }, [h(VideoAbstractDisplay, { video })]) }), { global: { plugins: [i18n] } });
        cy.get('.descriptions dt').eq(0).should('have.text', 'time');
        cy.get('.descriptions dd').eq(0).should('have.text', 'c16_30_150');
        cy.get('.descriptions [role=img]').should('have.attr', 'aria-label', 'false').and('have.class', 'text-danger').find('.pi-times').should('exist');
        cy.get('.descriptions dd').eq(2).should('contain.text', '100').and('contain.text', '12.345');
        cy.get('.description-width-3').should(($item) => {
            expect(getComputedStyle($item[0]).gridColumnEnd).to.equal('span 1');
        });
        cy.then(() => {
            videoDescriptionStore.columns.value = [];
        });
        cy.get('.descriptions').should('not.exist');
    });
});
