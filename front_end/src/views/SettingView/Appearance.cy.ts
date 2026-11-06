import { defineComponent, h } from 'vue';

import Appearance from './Appearance.vue';

import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import i18n from '@/i18n';
import { local } from '@/store';
import { ViennaIconLegacy, ViennaIconNew } from '@/utils/assets';

describe('<Appearance /> local switches', () => {
    const originalLegacy = local.value.vienna_logo_legacy;
    const originalExperimental = local.value.experimental;

    beforeEach(() => {
        local.value.vienna_logo_legacy = false;
        local.value.experimental = false;
    });

    afterEach(() => {
        local.value.vienna_logo_legacy = originalLegacy;
        local.value.experimental = originalExperimental;
    });

    it('persists both preferences and updates the RMV icon through labels and the keyboard', () => {
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [h(Appearance), h(SoftwareIcon, { software: 'r', 'data-cy': 'rmv-icon-preview' })]),
        }), { global: { plugins: [i18n] } });
        cy.get('[data-cy=vienna-logo-switch] input').should('not.be.checked').and('have.attr', 'aria-label', 'RMV logo');
        cy.get('[data-cy=rmv-icon-preview]').should('have.attr', 'src', ViennaIconNew);
        cy.get('[data-cy=vienna-logo-switch]').click('left');
        cy.get('[data-cy=vienna-logo-switch] input').should('be.checked');
        cy.get('[data-cy=rmv-icon-preview]').should('have.attr', 'src', ViennaIconLegacy);
        cy.get('[data-cy=experimental-switch] input').should('not.be.checked').focus();
        cy.realPress('Space');
        cy.get('[data-cy=experimental-switch] input').should('be.checked');
        cy.window().its('localStorage').invoke('getItem', 'local').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as Record<string, unknown>;
            expect(settings).to.include({ vienna_logo_legacy: true, experimental: true });
        });
        cy.then(() => {
            local.value.vienna_logo_legacy = false;
            local.value.experimental = false;
        });
        cy.get('[data-cy=vienna-logo-switch] input').should('not.be.checked');
        cy.get('[data-cy=experimental-switch] input').should('not.be.checked');
        cy.get('[data-cy=rmv-icon-preview]').should('have.attr', 'src', ViennaIconNew);
    });
});
