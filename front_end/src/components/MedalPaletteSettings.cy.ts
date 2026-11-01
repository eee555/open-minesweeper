import MedalPaletteSettings from './MedalPaletteSettings.vue';

import i18n from '@/i18n';
import { resetMedalPalette } from '@/services/medalPaletteStore';

describe('medal palette settings', () => {
    const originalLocale = i18n.global.locale.value;
    beforeEach(() => {
        i18n.global.locale.value = 'en';
        resetMedalPalette();
    });
    afterEach(() => {
        i18n.global.locale.value = originalLocale;
    });
    it('previews every series and difficulty using the shared renderer', () => {
        cy.mount(MedalPaletteSettings, { global: { plugins: [i18n] } });
        cy.get('.medal-colors select option').should('have.length', 24);
        cy.get('.medal-colors select').select('ability.stnb.nf.e');
        cy.get('.medal-colors .medal-graphic').should('have.length', 5);
        cy.get('.medal-colors .fixed-badge').should('have.length', 5);
        cy.get('.medal-colors .difficulty').first().should('have.attr', 'src').and('contain', '/difficulty/e.webp');
    });
    it('applies a complete HEX value without waiting for blur', () => {
        cy.mount(MedalPaletteSettings, { global: { plugins: [i18n] } });
        cy.get('.palette-row .hex').first().clear();
        cy.get('.palette-row .hex').first().type('#123456');
        cy.get('.palette-row image').first().should('have.attr', 'filter', 'url(#medal-soft-123456)');
        cy.get('.medal-colors [role=status]').should('have.text', 'Personal colors saved in this browser.');
    });
});
