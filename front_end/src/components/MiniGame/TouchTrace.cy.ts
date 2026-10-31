import { defineComponent, h, shallowReactive } from 'vue';

import Board from './Board.vue';
import TouchTrace from './TouchTrace.vue';

import { multiTouchModes } from '@/utils/minigame/leftClickTraining';
import { rebuildTouchReplay } from '@/utils/minigame/touchReplay';

describe('minigame TouchTrace adapter', () => {
    it('keeps interleaved contacts, cancellation and rewind aligned with the recording', () => {
        const replay = rebuildTouchReplay(multiTouchModes[2], {
            version: 1,
            cellSize: 32,
            initialBoard: 'AP////////8',
            events: [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0], [10, 32, 0, 0, 1], [10, -32, 0, 1, 3], [10, 32, 0, 0, 2], [10, -64, 32, 2, 0]],
        }, 50);
        const recording = JSON.stringify(replay.recording);
        const state = shallowReactive({ eventIndex: -1, transposed: false, size: 32 });
        cy.mount(defineComponent({ expose: [],
            render: () => h(Board, {
                board: replay.initialBoard, size: state.size, transposed: state.transposed, label: 'Touch replay', disabled: true,
            }, { overlay: () => h(TouchTrace, { replay, eventIndex: state.eventIndex, transposed: state.transposed }) }) }));
        cy.get('.minigame-touch-trace').should('have.css', 'pointer-events', 'none');
        cy.get('.minigame-touch-trace > rect').should('have.attr', 'opacity', '0');
        cy.get('[data-touch-path]').should('not.exist');

        cy.then(() => {
            state.eventIndex = 2;
        });
        cy.get('[data-touch-active]').should('have.length', 2);
        cy.get('[data-touch-down] circle').should('have.attr', 'r', '0.125');
        cy.get('[data-touch-active="0"]').should('have.attr', 'transform', 'translate(2.5 0.5)');
        cy.get('[data-touch-active="1"]').should('have.attr', 'transform', 'translate(1.5 0.5)');

        cy.then(() => {
            state.eventIndex = 3;
        });
        cy.get('[data-touch-active]').should('have.length', 1);
        cy.get('[data-touch-active="1"]').should('not.exist');
        cy.get('[data-touch-path]').should('have.length', 2);
        cy.get('[data-touch-down]').should('have.length', 2);
        cy.then(() => {
            state.eventIndex = 4;
        });
        cy.get('[data-touch-active]').should('not.exist');

        // A recording may end with a finger still down; it stays visible.
        cy.then(() => {
            state.eventIndex = 5;
        });
        cy.get('[data-touch-active="2"]').should('have.attr', 'transform', 'translate(0.5 1.5)');
        cy.get('[data-touch-path]').should('have.length', 3);
        cy.then(() => {
            state.transposed = true; state.size = 40;
        });
        cy.get('.minigame-touch-trace').should('have.attr', 'width', '320');
        cy.get('[data-touch-active="2"]').should('have.attr', 'transform', 'translate(1.5 0.5)');
        cy.then(() => {
            state.eventIndex = 1;
        });
        cy.get('[data-touch-active]').should('have.length', 2);
        cy.get('[data-touch-path]').should('have.length', 2);
        cy.get('[data-touch-active="1"]').should('have.attr', 'transform', 'translate(0.5 1.5)');
        cy.then(() => {
            state.eventIndex = -1;
        });
        cy.get('[data-touch-path]').should('not.exist');
        cy.get('[data-touch-active]').should('not.exist');
        cy.then(() => {
            expect(JSON.stringify(replay.recording)).to.eq(recording);
        });
    });
});
