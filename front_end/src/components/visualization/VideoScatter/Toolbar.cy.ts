import Toolbar from './Toolbar.vue';

import i18n from '@/i18n';
import { VideoScatterConfig } from '@/store';
import { pinia } from '@/store/create';

describe('<VideoScatter Toolbar /> metrics', () => {
    const originalConfig = { ...VideoScatterConfig.value };

    afterEach(() => {
        Object.assign(VideoScatterConfig.value, originalConfig);
    });

    it('persists all three metric selections and keeps them usable when the container shrinks', () => {
        Object.assign(VideoScatterConfig.value, { x: 'bv', y: 'time', colorBy: 'level' });
        cy.mount(Toolbar, { attrs: { style: { width: '360px' } }, global: { plugins: [i18n, pinia] } });
        cy.get('select[aria-label=x]').select('bvs');
        cy.get('select[aria-label=y]').select('ioe');
        cy.get('select[aria-label="Color by"]').select('cls');
        cy.wrap(VideoScatterConfig).its('value').should('include', { x: 'bvs', y: 'ioe', colorBy: 'cls' });
        cy.window().its('localStorage').invoke('getItem', 'video-scatter-config').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as { x?: string; y?: string; colorBy?: string };
            expect(settings).to.include({ x: 'bvs', y: 'ioe', colorBy: 'cls' });
        });

        cy.get('.video-scatter-toolbar').invoke('css', 'width', '220px');
        cy.get('.video-scatter-toolbar__metrics select').should(($selects) => {
            expect($selects).to.have.length(3);
            const container = Cypress.$('.video-scatter-toolbar')[0].getBoundingClientRect();
            for (const select of $selects.toArray()) {
                const bounds = select.getBoundingClientRect();
                expect(bounds.width).to.be.greaterThan(0);
                expect(bounds.left).to.be.at.least(container.left - 0.5);
                expect(bounds.right).to.be.at.most(container.right + 0.5);
            }
        });
        cy.get('select[aria-label=x]').select('rqp');
        cy.wrap(VideoScatterConfig).its('value.x').should('eq', 'rqp');

        cy.get('.video-scatter-toolbar').invoke('css', 'width', '480px');
        cy.get('select[aria-label=x]').should('have.value', 'rqp');
        cy.get('select[aria-label=y]').should('have.value', 'ioe');
        cy.get('select[aria-label="Color by"]').should('have.value', 'cls');
    });
});
