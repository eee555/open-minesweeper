import MedalArt from './MedalArt.vue';

import i18n from '@/i18n';
import { defaultMedalPalette } from '@/services/medalPalette';
import { resetMedalPalette, updateMedalPalette } from '@/services/medalPaletteStore';

describe('template-based medal art', () => {
    beforeEach(() => {
        resetMedalPalette();
    });
    it('shares the body image, applies score colors and keeps numbers in HTML/CSS', () => {
        cy.mount(MedalArt, { props: { series: 'b', code: 'ability.time.b', stage: 10000, size: 72 }, global: { plugins: [i18n] } });
        cy.get('.medal-graphic').should('have.attr', 'data-score-tier', '2');
        cy.get('image').should('have.attr', 'href').and('contain', 'breakthrough.webp?v=6');
        cy.get('.plate').should('have.text', '10');
        cy.get('.difficulty').should('have.attr', 'src').and('contain', '/difficulty/b.webp');
        cy.then(() => {
            const config = defaultMedalPalette(); config.colors[1] = '#123456'; updateMedalPalette(config);
        });
        cy.get('image').should('have.attr', 'filter', 'url(#medal-soft-123456)');
    });
    it('preserves an NF badge in an unfiltered layer', () => {
        cy.mount(MedalArt, { props: { series: 'mn', code: 'ability.stnb.nf.e', stage: 100, size: 48 }, global: { plugins: [i18n] } });
        cy.get('.fixed-badge').should('have.attr', 'clip-path');
        cy.get('.fixed-badge').should('not.have.attr', 'filter');
        cy.get('mask circle').should('have.attr', 'fill', 'black');
        cy.get('.difficulty').should('have.attr', 'src').and('contain', '/difficulty/e.webp');
    });
    for (const size of [32, 48, 72]) {
        it(`keeps numbers legible and outside the centered body at ${size}px`, () => {
            cy.mount(MedalArt, { props: { series: 'm', code: 'ability.stnb.e', stage: 100, size }, global: { plugins: [i18n] } });
            cy.get('.plate').should('have.css', 'font-size', '14px').and('have.css', 'background-color', 'rgba(0, 0, 0, 0)');
            cy.get('.medal-graphic').then(($graphic) => {
                const art = $graphic.find('.art-stage')[0].getBoundingClientRect();
                const body = $graphic.find('.medal-body')[0].getBoundingClientRect();
                const number = $graphic.find('.plate')[0].getBoundingClientRect();
                expect(Math.abs(body.x + body.width / 2 - art.x - art.width / 2)).to.be.lessThan(1);
                expect(Math.abs(body.y + body.height / 2 - art.y - art.height / 2)).to.be.lessThan(1);
                expect(number.top).to.be.at.least(art.bottom);
            });
        });
    }
});
