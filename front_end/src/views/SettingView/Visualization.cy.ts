import Visualization from './Visualization.vue';

import i18n from '@/i18n';
import { colorTheme, local } from '@/store';
import { pinia } from '@/store/create';
import { colorSchemeTemplates } from '@/utils/config';

describe('<Visualization />', () => {
    const originalBvs = colorTheme.value.bvs;
    const originalGrade = colorTheme.value.grade;
    const originalIoe = colorTheme.value.ioe;
    const originalExperimental = local.value.experimental;
    const originalColored = local.value.colored;

    afterEach(() => {
        colorTheme.value.bvs = originalBvs;
        colorTheme.value.grade = originalGrade;
        colorTheme.value.ioe = originalIoe;
        local.value.experimental = originalExperimental;
        local.value.colored = originalColored;
    });

    it('restores only the selected palette without sharing the default template arrays', () => {
        local.value.experimental = true;
        colorTheme.value.bvs = { thresholds: [1], colors: ['#000000', '#ffffff'] };
        colorTheme.value.grade = { thresholds: [], colors: [] };
        cy.mount(Visualization, { global: { plugins: [i18n, pinia] } });

        cy.contains('button', 'Restore Default').click();
        cy.then(() => {
            expect(colorTheme.value.bvs).to.deep.equal(colorSchemeTemplates.ArbiterStatsAuto.bvs);
            expect(colorTheme.value.grade).to.deep.equal({ thresholds: [], colors: [] });
            colorTheme.value.bvs.thresholds[0] = 0.02;
            expect(colorSchemeTemplates.ArbiterStatsAuto.bvs.thresholds[0]).to.equal(0.01);
        });

        cy.get('select[aria-label="Piecewise Palette"]').select('grade');
        cy.contains('button', 'Restore Default').click();
        cy.then(() => {
            expect(colorTheme.value.grade).to.deep.equal(colorSchemeTemplates.ArbiterStatsAuto.grade);
            expect(colorTheme.value.bvs.thresholds[0]).to.equal(0.02);
            colorTheme.value.ioe = { thresholds: [1], colors: ['#000000', '#ffffff'] };
        });

        cy.get('select[aria-label="Piecewise Palette"]').select('ioe');
        cy.get('.color-scheme-setting__threshold:not([readonly])').first().invoke('val', '1.5').trigger('input');
        cy.then(() => {
            expect(colorTheme.value.ioe.thresholds).to.deep.equal([1.5]);
        });
        cy.window().its('localStorage').invoke('getItem', 'colorTheme').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as { ioe?: { thresholds: number[] } };
            expect(settings.ioe?.thresholds).to.deep.equal([1.5]);
        });
        cy.contains('button', 'Restore Default').click();
        cy.then(() => {
            expect(colorTheme.value.ioe).to.deep.equal(colorSchemeTemplates.ArbiterStatsAuto.ioe);
            expect(colorTheme.value.bvs.thresholds[0]).to.equal(0.02);
        });
    });

    it('shares and persists the coloring switch even without experimental settings enabled', () => {
        local.value.experimental = false;
        local.value.colored = false;
        cy.mount(Visualization, { global: { plugins: [i18n, pinia] } });
        cy.get('select[aria-label="Piecewise Palette"]').should('not.exist');
        cy.get('[data-cy=coloring-switch]').should('be.visible').find('[role=switch]').should('have.attr', 'aria-checked', 'false');
        cy.get('[data-cy=coloring-switch]').click();
        cy.get('[data-cy=coloring-switch] [role=switch]').should('have.attr', 'aria-checked', 'true');
        cy.window().its('localStorage').invoke('getItem', 'local').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as { colored?: boolean };
            expect(settings.colored).to.equal(true);
        });
        cy.then(() => {
            local.value.colored = false;
        });
        cy.get('[data-cy=coloring-switch] [role=switch]').should('have.attr', 'aria-checked', 'false');
    });
});
