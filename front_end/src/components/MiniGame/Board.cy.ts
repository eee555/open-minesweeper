import type { BoardBackground, MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import { defineComponent, h } from 'vue';

import Board from './Board.vue';

import type { TrainingTouchInput } from '@/utils/minigame/touchRecording';
import { mouseAt, touchAt } from '@cy/support/minigame';

function mountBoard(board: number[][]) {
    cy.mount(defineComponent({ expose: [], render: () => h(Board, { board, size: 32, label: 'Test board' }) })).then(({ wrapper }) => {
        cy.wrap(wrapper.findComponent(Board)).as('board');
    });
}

describe('shared minigame press preview', () => {
    it('scrolls with one finger, stops with two and continues after a contact is cancelled', () => {
        cy.viewport(800, 600);
        cy.window().then((win) => cy.stub(win.HTMLElement.prototype, 'setPointerCapture'));
        cy.mount(defineComponent({ expose: [],
            render: () => h('div', { style: { width: '240px', height: '200px', overflow: 'auto' }, 'data-cy': 'touch-scroll' }, [
                h(Board, { board: Array.from({ length: 30 }, () => Array.from({ length: 30 }, () => 10)), size: 32, label: 'Scrollable board', input: 'touch' }),
            ]) }));
        const pointer = (type: string, pointerId: number, clientX: number, clientY: number) => {
            cy.get('[data-cy="minigame-board"]').then(($board) => {
                const rect = $board[0].getBoundingClientRect();
                cy.wrap($board).trigger(type, clientX - rect.left, clientY - rect.top, { eventConstructor: 'PointerEvent', pointerId, pointerType: 'touch', clientX, clientY, scrollBehavior: false });
            });
        };
        cy.get('[data-cy="minigame-board"]').then(($board) => {
            const { left, top } = $board[0].getBoundingClientRect();
            pointer('pointerdown', 1, left + 150, top + 150);
            pointer('pointermove', 1, left + 100, top + 100);
            cy.get('[data-cy="touch-scroll"]').should(($scroll) => {
                expect($scroll[0].scrollLeft).to.eq(50);
                expect($scroll[0].scrollTop).to.eq(50);
            });
            pointer('pointerdown', 2, left + 120, top + 120);
            pointer('pointermove', 1, left + 60, top + 60);
            cy.get('[data-cy="touch-scroll"]').should('have.prop', 'scrollTop', 50);
            pointer('pointercancel', 2, left + 120, top + 120);
            pointer('pointermove', 1, left + 50, top + 50);
            cy.get('[data-cy="touch-scroll"]').should('have.prop', 'scrollTop', 60);
            pointer('pointerup', 1, left + 50, top + 50);
        });
    });

    it('records independent contacts without press previews and cancels held contacts on blur', () => {
        cy.window().then((win) => cy.stub(win.HTMLElement.prototype, 'setPointerCapture'));
        cy.mount(defineComponent({ expose: [], render: () => h(Board, { board: [[10, 16, 11], [10, 10, 10]], size: 32, label: 'Touch board', input: 'touch', recordTouch: true }) })).then(({ wrapper }) => {
            cy.wrap(wrapper.findComponent(Board)).as('board');
        });
        touchAt(0, 0, 'pointerdown');
        touchAt(0, 1, 'pointerdown', 2);
        touchAt(0, 2, 'pointerdown', 3);
        cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
        });
        touchAt(0, 0, 'pointercancel');
        touchAt(1, 1, 'pointermove', 2);
        cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
            expect(wrapper.emitted('action')).to.have.length(3);
        });
        cy.window().trigger('blur');
        touchAt(1, 1, 'pointerup', 2);
        cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
            expect(wrapper.emitted('action')).to.have.length(3);
            expect(wrapper.emitted<[TrainingTouchInput]>('touchRecord')?.map(([input]) => [input.pointerId, input.action])).to.deep.eq([
                [1, 'down'], [2, 'down'], [3, 'down'], [1, 'cancel'], [2, 'move'], [2, 'cancel'], [3, 'cancel'],
            ]);
        });
    });

    for (const order of ['left-first', 'right-first']) {
        it(`previews a moving 3x3 region except flags and clears on first release (${order})`, () => {
            const board = Array.from({ length: 5 }, () => [10, 10, 10, 10, 10]);
            board[1][1] = 11;
            board[1][2] = 16;
            board[2][2] = 2;
            mountBoard(board);
            cy.get('.minigame-board-foreground').should('have.css', 'opacity', '1');
            if (order === 'left-first') {
                mouseAt(2, 2, 'mousedown');
                mouseAt(2, 2, 'mousedown', 2, 3);
            } else {
                mouseAt(2, 2, 'mousedown', 2, 2);
                mouseAt(2, 2, 'mousedown', 0, 3);
            }
            cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
                const background = wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board');
                expect(background).to.deep.eq([
                    [false, false, false, false, false], [false, false, true, true, false], [false, true, true, true, false], [false, true, true, true, false], [false, false, false, false, false],
                ]);
                expect(wrapper.findComponent<typeof MinesweeperBoard>('.minesweeper-board-content').props('board')).to.deep.eq(board);
            });
            mouseAt(0, 0, 'mousemove', 0, 3);
            cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
                const background = wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board');
                expect(background?.[0][0]).to.eq(true);
                expect(background?.[1][1]).to.eq(false);
                expect(background?.[3][3]).to.eq(false);
            });
            mouseAt(0, 0, 'mouseup', 2, 1);
            cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
                expect(wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
                expect(wrapper.emitted('action')?.filter(([action]) => action === 'chord')).to.have.length(1);
            });
            mouseAt(0, 0, 'mouseup');
        });
    }

    it('cancels held buttons without generating a chord on blur', () => {
        mountBoard([[10, 16, 11], [10, 2, 10], [10, 10, 10]]);
        mouseAt(1, 1, 'mousedown');
        mouseAt(1, 1, 'mousedown', 2, 3);
        cy.window().trigger('blur');
        mouseAt(1, 1, 'mouseup', 0, 2);
        mouseAt(1, 1, 'mouseup', 2, 0);
        cy.get<ComponentWrapper<typeof Board>>('@board').should((wrapper) => {
            expect(wrapper.emitted('action')).to.eq(undefined);
            expect(wrapper.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
        });
    });
});
