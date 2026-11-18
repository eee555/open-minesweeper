import ReactionAnalysis from './ReactionAnalysis.vue';

import i18n from '@/i18n';
import { hoverReactionBar } from '@cy/support/minigame';

describe('reaction analysis tooltips', () => {
    it('previews reaction end times and highlights every matching histogram sample within its click type', () => {
        cy.viewport(1200, 900);
        cy.mount(ReactionAnalysis, {
            props: { samples: [
                { previousUpMs: 0, downMs: 80, upMs: 105, jump: false },
                { previousUpMs: 105, downMs: 215, upMs: 325, jump: true },
                { previousUpMs: 325, downMs: 400, upMs: 434, jump: false },
                { previousUpMs: 434, downMs: 500, upMs: 539, jump: true },
            ] },
            attrs: { onPreview: cy.stub().as('preview') },
            global: { plugins: [i18n] },
        });
        cy.get('[data-cy=reaction-analysis] svg title').should('not.exist');
        hoverReactionBar('reaction-bars');
        cy.get('.tippy-box[data-state=visible] [data-cy=reaction-chart-tooltip]').should('be.visible').
            and('contain.text', 'Previous release: 0 ms').and('contain.text', 'Current press: 80 ms').and('contain.text', 'Current release: 105 ms').
            and('contain.text', 'Release to press: 80 ms').and('contain.text', 'Press to release: 25 ms').and('contain.text', 'Total interval: 105 ms');
        cy.get('@preview').should('have.been.calledWith', 105);
        cy.get('[data-cy=reaction-bars] .reaction-chart').trigger('pointerleave');
        cy.get('.tippy-box[data-state=visible]').should('not.exist');
        cy.get('@preview').its('lastCall.args').should('deep.equal', [null]);
        for (const [chart, index, content, highlights] of [
            ['reaction-adjacent-histogram', 10, '0.100–0.110 s: 2', ['0', '2']],
            ['reaction-jump-histogram', 10, '0.100–0.110 s: 1', ['3']],
            ['reaction-jump-histogram', 22, '0.220–0.230 s: 1', ['1']],
        ] as const) {
            hoverReactionBar(chart, index);
            cy.get('.tippy-box[data-state=visible] [data-cy=reaction-chart-tooltip]').should('be.visible').and('have.text', content);
            cy.get('[data-cy=reaction-bar-highlight]').should(($bars) => {
                expect($bars.toArray().map((bar) => bar.getAttribute('data-index'))).to.deep.equal(highlights);
            });
            cy.get(`[data-cy=${chart}] .reaction-chart`).trigger('pointerleave');
            cy.get('.tippy-box[data-state=visible]').should('not.exist');
            cy.get('[data-cy=reaction-bar-highlight]').should('not.exist');
        }
    });
});
