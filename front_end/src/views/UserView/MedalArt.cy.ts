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
    it('keeps the default number row outside the centered body', () => {
        cy.mount(MedalArt, { props: { series: 'm', code: 'ability.stnb.e', stage: 100, size: 32 }, global: { plugins: [i18n] } });
        cy.get('.plate').should('have.text', '100');
        cy.get('.medal-graphic').should(($graphic) => {
            const art = $graphic.find('.art-stage')[0].getBoundingClientRect();
            const body = $graphic.find('.medal-body')[0].getBoundingClientRect();
            const number = $graphic.find('.plate')[0].getBoundingClientRect();
            expect(Math.abs(body.x + body.width / 2 - art.x - art.width / 2)).to.be.lessThan(1);
            expect(Math.abs(body.y + body.height / 2 - art.y - art.height / 2)).to.be.lessThan(1);
            expect(number.top).to.be.at.least(art.bottom);
        });
    });
    for (const size of [32, 56, 64, 80]) {
        it(`keeps a long corner number visible without adding a row at ${size}px`, () => {
            cy.mount(MedalArt, { props: { series: 'h', code: 'shareholder.origin', stage: 100000, size, cornerPlate: true }, global: { plugins: [i18n] } });
            cy.get('.plate').should('not.exist');
            cy.get('.corner-plate').should('have.text', '100000').and('be.visible');
            cy.get('.medal-graphic').should(($graphic) => {
                const art = $graphic.find('.art-stage')[0].getBoundingClientRect();
                const number = $graphic.find('.corner-plate')[0].getBoundingClientRect();
                expect($graphic[0].getBoundingClientRect().height).to.be.closeTo(size, 1);
                expect(number.top).to.be.greaterThan(art.top + art.height / 2);
                expect(number.right).to.be.closeTo(art.right, 5);
                expect(number.left).to.be.at.least(art.left - 5);
                expect(number.bottom).to.be.closeTo(art.bottom, 3);
            });
        });
    }
    it('keeps a medal without a number at icon height in corner mode', () => {
        cy.mount(MedalArt, { props: { series: 'r', code: 'novice.realname', stage: 1, size: 48, cornerPlate: true }, global: { plugins: [i18n] } });
        cy.get('.corner-plate').should('not.exist');
        cy.get('.medal-graphic').invoke('outerHeight').should('be.closeTo', 48, 1);
    });
});
