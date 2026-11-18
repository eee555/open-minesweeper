import { defineComponent, h } from 'vue';

import App from './App.vue';

import i18n from '@/i18n';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { chordAt, hoverReactionBar, isolateMinigameHistory, mouseAt, savedMinigameResults, touchAt } from '@cy/support/minigame';

describe('reaction training input', () => {
    isolateMinigameHistory();
    beforeEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });

    it('saves successful time pairs, displays the three charts, and seeks without saving again', () => {
        let now = 0;
        cy.window().then((win) => {
            cy.stub(win.Math, 'random').returns(0.99);
            cy.stub(win.performance, 'now').callsFake(() => now);
        });
        cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } });
        for (let index = 0; index < 14; index++) {
            cy.then(() => {
                now = index * 100;
            });
            mouseAt(0, index % 4, 'mousedown');
            cy.then(() => {
                now = index * 100 + 20;
            });
            mouseAt(0, index % 4, 'mouseup');
        }
        cy.get('[data-cy=reaction-training]').should('have.attr', 'data-phase', 'won');
        cy.get('[data-cy=reaction-bars] .plot-bar').first().find('rect').should('have.length', 10);
        cy.get('[data-cy=reaction-adjacent-histogram], [data-cy=reaction-jump-histogram]').should('have.length', 2);
        savedMinigameResults().should((entries) => {
            expect(entries).to.have.length(1);
            const [entry] = entries;
            if (entry.game !== 'reaction') throw new Error('Expected reaction history');
            expect(entry.scoreMs).to.eq(1300);
            expect(entry.replay.clicks).to.have.length(14);
            expect(Object.keys(entry.replay).sort()).to.deep.eq(['clicks', 'draws', 'sides', 'version']);
        });
        cy.get('[data-cy=minigame-replay-position]').invoke('val', '400').trigger('input');
        hoverReactionBar('reaction-bars');
        cy.get('[data-cy=minigame-replay-position]').should('have.value', '100');
        cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', '009');
        cy.get('[data-cy=reaction-time]').should('have.attr', 'aria-label', '000.100');
        cy.get('[data-cy=minigame-replay-play]').should('have.attr', 'aria-pressed', 'false');
        cy.get('[data-cy=reaction-bars] .reaction-chart').trigger('pointerleave');
        cy.get('[data-cy=minigame-replay-position]').should('have.value', '400');
        cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', '007');
        cy.get('[data-cy=minigame-replay-play]').should('have.attr', 'aria-pressed', 'false');
        savedMinigameResults().should('have.length', 1);
    });
    it('uses fixed horizontal lengths and reaction targets for each level', () => {
        cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } });
        for (const [level, length, count] of [['b', 5, '010'], ['i', 10, '020'], ['e', 20, '040']] as const) {
            cy.get(`[data-cy=reaction-training] input[value=${level}]`).parent().click();
            cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', count);
            cy.get('[data-cy=minigame-board]').should(($board) => {
                const rect = $board[0].getBoundingClientRect();
                expect(rect.width / rect.height).to.be.closeTo(length / 2, 0.01);
            });
        }
    });

    for (const input of ['mouse', 'touch']) {
        it(`starts on ${input} release and ignores right clicks and chords`, () => {
            cy.window().then((win) => {
                cy.stub(win.Math, 'random').returns(0.99);
                cy.stub(win.HTMLElement.prototype, 'setPointerCapture');
            });
            cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } });
            mouseAt(0, 0, 'mousedown', 2, 2);
            mouseAt(0, 0, 'mouseup', 2, 0);
            chordAt(0, 0);
            mouseAt(1, 0, 'mousedown');
            mouseAt(1, 0, 'mouseup');
            cy.get('[data-cy=reaction-training]').should('have.attr', 'data-phase', 'ready');
            if (input === 'touch') touchAt(0, 0, 'pointerdown');
            else mouseAt(0, 0, 'mousedown');
            cy.get('[data-cy=reaction-training]').should('have.attr', 'data-phase', 'ready');
            if (input === 'touch') touchAt(0, 0, 'pointerup');
            else mouseAt(0, 0, 'mouseup');
            cy.get('[data-cy=reaction-training]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', '010');
            if (input === 'touch') {
                touchAt(0, 1, 'pointerdown');
                touchAt(0, 1, 'pointerup');
            } else {
                mouseAt(0, 1, 'mousedown');
                mouseAt(0, 1, 'mouseup');
            }
            cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', '009');
            if (input === 'touch') {
                touchAt(0, 0, 'pointerdown');
                touchAt(0, 0, 'pointerup');
                touchAt(1, 0, 'pointerdown');
                touchAt(1, 0, 'pointerup');
            } else {
                mouseAt(0, 0, 'mousedown');
                mouseAt(0, 0, 'mouseup');
                mouseAt(1, 0, 'mousedown');
                mouseAt(1, 0, 'mouseup');
            }
            cy.get('[data-cy=reaction-training]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy=reaction-remaining]').should('have.attr', 'aria-label', '009');
        });
    }
});
