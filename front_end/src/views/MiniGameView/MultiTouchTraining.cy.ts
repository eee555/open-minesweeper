import type { MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import { transpose } from 'd3-array';
import { defineComponent, h } from 'vue';

import App from './LeftClickTraining/App.vue';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import type TouchTrace from '@/components/MiniGame/TouchTrace.vue';
import i18n from '@/i18n';
import { encodeMines } from '@/utils/minigame/boardEncoding';
import { multiTouchModes } from '@/utils/minigame/leftClickTraining';
import type { AnyTrainingReplay } from '@/utils/minigame/replay';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { isolateMinigameHistory, mouseAt, savedMinigameResults, touchAt } from '@cy/support/minigame';

function mountGame(gameType: 'multi-touch' | 'left-click' = 'multi-touch') {
    return cy.mount(defineComponent({ expose: [], render: () => h(App, { offline: true, gameType }) }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
        cy.wrap(wrapper.findComponent(App)).as('game');
    });
}

function cells(board: number[][], value: number) {
    return board.flatMap((row, r) => row.flatMap((cell, c) => (cell === value ? [{ row: r, column: c }] : [])));
}

describe('touch-only training', () => {
    isolateMinigameHistory();
    beforeEach(() => {
        cy.viewport(1280, 900);
        minigameSettings.value = defaultMinigameSettings();
        cy.window().then((win) => cy.stub(win.HTMLElement.prototype, 'setPointerCapture'));
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
        cy.document().then((doc) => {
            Reflect.deleteProperty(doc, 'fullscreenElement');
            Reflect.deleteProperty(doc, 'fullScreen');
        });
    });

    it('transposes Expert locally without changing game or replay coordinates', () => {
        cy.viewport(1280, 1400);
        mountGame();
        cy.get('[data-cy="training-orientation"]').should('not.exist');
        cy.get('[data-cy="training-level"] input[value="e"]').parent().click();
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '240');
        cy.get<ComponentWrapper<typeof App>>('@game').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            expect(board).to.have.length(16);
            expect(board[0]).to.have.length(30);
            const [safe] = cells(board, 10).filter(({ row, column }) => row !== column);
            const [mine] = cells(board, 16);
            cy.get('[data-cy="training-orientation"] input[value="vertical"]').parent().click();
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                expect(game.findComponent<typeof MinesweeperBoard>('.minesweeper-board-content').props('board')).to.deep.eq(transpose(board));
            });
            touchAt(safe.column, safe.row, 'pointerdown');
            touchAt(safe.column, safe.row, 'pointerup');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="training-orientation"] input[value="horizontal"]').parent().click();
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            const opened = board.map((row, r) => row.map((cell, c) => (r === safe.row && c === safe.column ? 0 : cell)));
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                expect(game.findComponent<typeof MinesweeperBoard>('.minesweeper-board-content').props('board')).to.deep.eq(opened);
            });
            touchAt(mine.row, mine.column, 'pointerdown', 2);
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'lost');
            touchAt(safe.row, safe.column, 'pointerdown', 3);
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '239');
            cy.get<ComponentWrapper<typeof App>>('@game').then((game) => {
                const replay: AnyTrainingReplay = game.findComponent<typeof TouchTrace>('.minigame-touch-trace').props('replay');
                expect(replay.mode.rows).to.eq(16);
                expect(replay.mode.columns).to.eq(30);
                expect(replay.recording.initialBoard).to.eq(encodeMines(multiTouchModes[6], board));
                expect(replay.recording.events[0]).to.deep.eq([0, (safe.column + 0.5) * 32, (safe.row + 0.5) * 32, 0, 0]);
                const recording = structuredClone(replay.recording);
                cy.get('[data-cy="training-orientation"] input[value="vertical"]').parent().click();
                cy.get('.minigame-touch-trace').should('have.attr', 'width', '512').and('have.attr', 'height', '960');
                cy.get('.minigame-touch-trace > g').should('have.attr', 'transform', 'matrix(0 1 1 0 0 0)');
                cy.get<ComponentWrapper<typeof App>>('@game').should((current) => {
                    const currentReplay: AnyTrainingReplay = current.findComponent<typeof TouchTrace>('.minigame-touch-trace').props('replay');
                    expect(currentReplay.recording).to.deep.eq(recording);
                });
                cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'lost');
                cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value) => {
                    expect(JSON.parse(String(value))).to.have.property('multiTouchOrientation', 'vertical');
                });
            });
        });
        savedMinigameResults().should('have.length', 0);
    });

    it('shares an editable fullscreen cell size and keeps the game and size when resizing and exiting', () => {
        // Mock the browser API because native fullscreen is unavailable in the CT iframe.
        cy.window().then((win) => {
            let target: Element | null = null;
            Object.defineProperty(win.document, 'fullscreenElement', { configurable: true, get: () => target });
            Object.defineProperty(win.document, 'fullScreen', { configurable: true, get: () => target !== null });
            cy.stub(win.HTMLElement.prototype, 'requestFullscreen').callsFake(() => {
                target = win.document.querySelector('[data-cy="training-game"]');
                win.document.dispatchEvent(new win.Event('fullscreenchange'));
                return Promise.resolve();
            });
            cy.stub(win.document, 'exitFullscreen').callsFake(() => {
                target = null;
                win.document.dispatchEvent(new win.Event('fullscreenchange'));
                return Promise.resolve();
            });
        });
        cy.viewport(400, 800);
        mountGame();
        cy.get('[data-cy="training-level"] input[value="e"]').parent().click();
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '240');
        cy.get('.training-frame').should('have.class', 'outer-border');
        cy.get('.training-frame .inner-border').should('have.length', 2);
        cy.get('[data-cy="training-restart"]').should('not.exist');
        cy.get('[data-cy="training-cell-size"]').should('not.exist');
        cy.get<ComponentWrapper<typeof App>>('@game').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const [safe] = cells(board, 10);
            cy.get('[data-cy="minigame-board"]').scrollIntoView();
            cy.get('.training-scroll').scrollTo(safe.column * 32, 0);
            cy.get('[data-cy="minigame-board"]').then(($board) => {
                const rect = $board[0].getBoundingClientRect();
                const x = (safe.column + 0.5) * 32;
                const y = (safe.row + 0.5) * 32;
                const position = { eventConstructor: 'PointerEvent', pointerId: 1, pointerType: 'touch', clientX: rect.left + x, clientY: rect.top + y, scrollBehavior: false as const };
                cy.get('[data-cy="minigame-board"]').trigger('pointerdown', x, y, position);
                cy.get('[data-cy="minigame-board"]').trigger('pointerup', x, y, position);
            });
            cy.get('[data-cy="training-fullscreen"]').click();
            cy.get('[data-cy="training-cell-size"]').should('have.attr', 'type', 'number').and('have.value', '32');
            cy.get('.training-frame').should('not.have.class', 'outer-border').and('have.css', 'border-top-width', '0px');
            cy.get('.training-frame .inner-border').should('not.exist');
            cy.get('.training-frame-counters').should('have.css', 'border-top-width', '0px');
            cy.get('.training-frame').should(($frame) => {
                const [frame] = $frame;
                const bar = frame.querySelector('.training-frame-counters');
                const boardElement = frame.querySelector('[data-cy="minigame-board"]');
                if (bar === null || boardElement === null) throw new Error('Missing board or counters');
                const frameRect = frame.getBoundingClientRect();
                const boardRect = boardElement.getBoundingClientRect();
                expect(boardRect.left).to.eq(frameRect.left);
                expect(boardRect.width).to.eq(frameRect.width);
                expect(boardRect.top).to.eq(bar.getBoundingClientRect().bottom);
            });
            const opened = board.map((row, r) => row.map((cell, c) => (r === safe.row && c === safe.column ? 0 : cell)));
            cy.get('.training-frame-counters').should('have.prop', 'tagName', 'DIV');
            cy.get('.training-scroll').scrollTo(0, 0);
            cy.get('.training-frame-counters').click('topLeft');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                expect(game.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board')).to.deep.eq(opened);
            });
            cy.viewport(420, 740);
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                expect(game.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('size')).to.eq(32);
            });
            cy.get('[data-cy="training-cell-size"]').clear();
            cy.get('[data-cy="training-cell-size"]').type('43');
            cy.get('[data-cy="training-cell-size"]').blur();
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                const component = game.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]');
                expect(component.props('board')).to.deep.eq(opened);
                expect(component.props('size')).to.eq(43);
            });
            cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value) => {
                expect(JSON.parse(String(value))).to.have.property('cellSize', 43);
            });
            cy.viewport(400, 700);
            cy.get('[data-cy="training-cell-size"]').should('have.value', '43');
            cy.get('[data-cy="minigame-board"]').should(($board) => {
                expect($board[0].getBoundingClientRect().width).to.eq(30 * 43);
            });
            cy.get('.training-scroll').should(($scroll) => {
                const [scroll] = $scroll;
                expect(scroll.scrollWidth).to.be.greaterThan(scroll.clientWidth);
                expect(scroll.scrollHeight).to.be.greaterThan(scroll.clientHeight);
            });
            cy.get('[data-cy="training-fullscreen"]').click();
            cy.get('[data-cy="training-fullscreen"]').should('have.attr', 'aria-pressed', 'false');
            cy.get('.training-frame').should('have.class', 'outer-border');
            cy.get('.training-frame .inner-border').should('have.length', 2);
            cy.get('.training-frame-counters').should('have.prop', 'tagName', 'BUTTON');
            cy.get('[data-cy="training-restart"]').should('not.exist');
            cy.get('[data-cy="training-cell-size"]').should('not.exist');
            cy.get<ComponentWrapper<typeof App>>('@game').should((game) => {
                const component = game.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]');
                expect(component.props('board')).to.deep.eq(opened);
                expect(component.props('size')).to.eq(43);
            });
        });
        cy.get('[data-cy="training-orientation"] input[value="vertical"]').parent().click();
        cy.get('[data-cy="training-fullscreen"]').click();
        cy.get('.training-scroll').should(($scroll) => {
            expect($scroll[0].scrollWidth).to.be.greaterThan($scroll[0].clientWidth);
            expect($scroll[0].scrollHeight).to.be.greaterThan($scroll[0].clientHeight);
        });
        cy.get<ComponentWrapper<typeof App>>('@game').then((game) => {
            const resets = game.emitted('reset')?.length ?? 0;
            cy.get('[data-cy="training-restart"]').click();
            cy.get<ComponentWrapper<typeof App>>('@game').should((current) => {
                expect(current.emitted('reset')).to.have.length(resets + 1);
            });
        });
        cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy="training-fullscreen"]').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-cy="training-fullscreen"]').click();
    });

    it('opens on each independent contact down, ignoring mouse, pen, movement and release', () => {
        mountGame();
        cy.get<ComponentWrapper<typeof App>>('@game').then((wrapper) => {
            const safe = cells(wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board'), 10);
            mouseAt(safe[0].row, safe[0].column, 'mousedown');
            mouseAt(safe[0].row, safe[0].column, 'mouseup');
            touchAt(safe[0].row, safe[0].column, 'pointerdown', 3, 'pen');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
            touchAt(safe[0].row, safe[0].column, 'pointerdown');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            touchAt(safe[1].row, safe[1].column, 'pointerdown', 2);
            touchAt(safe[2].row, safe[2].column, 'pointermove');
            touchAt(safe[2].row, safe[2].column, 'pointerup');
            touchAt(safe[1].row, safe[1].column, 'pointercancel', 2);
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '030');
            touchAt(safe[2].row, safe[2].column, 'pointerdown');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '029');
        });
    });

    it('saves a successful replay once and keeps it after seeking and restarting', () => {
        mountGame();
        cy.get('[data-cy="training-density"]').select('87.5');
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '008');
        cy.get<ComponentWrapper<typeof App>>('@game').then((wrapper) => {
            const safe = cells(wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board'), 10);
            safe.forEach(({ row, column }, index) => {
                touchAt(row, column, 'pointerdown', index + 1);
            });
        });
        cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'won');
        cy.get('[data-cy="minigame-replay-controls"]').should('be.visible');
        savedMinigameResults().should((results) => {
            expect(results).to.have.length(1);
            const [saved] = results;
            if (saved.game !== 'multi-touch') throw new Error('Wrong saved game');
            expect(saved.mode.rankingKey).to.eq('multi-touch-b-87.5-v1');
        });
        cy.get<ComponentWrapper<typeof App>>('@game').should((wrapper) => {
            const events = wrapper.emitted('completed');
            expect(events).to.have.length(1);
            expect(events?.[0][0]).to.eq('multi-touch-b-87.5-v1');
        });
        cy.get('[data-cy="minigame-replay-contact"]').should('have.length', 8);
        cy.get('.minigame-touch-trace polyline').should('have.length', 8);
        cy.get('[data-cy="minigame-replay-position"]').invoke('val', '0').trigger('input');
        cy.get('[data-cy="minigame-replay-position"]').trigger('change');
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '007');
        cy.get('[data-cy="minigame-replay-contact"]').should('have.length', 1);
        cy.get('.training-frame-counters').click();
        cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy="minigame-replay-controls"]').should('not.exist');
        savedMinigameResults().should('have.length', 1);
    });

    it('rejects touch and pen in mouse-only left-click training, including compatibility mouse events', () => {
        mountGame('left-click');
        cy.get<ComponentWrapper<typeof App>>('@game').then((wrapper) => {
            const [safe] = cells(wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board'), 10);
            for (const kind of ['touch', 'pen']) {
                touchAt(safe.row, safe.column, 'pointerdown', 1, kind);
                touchAt(safe.row, safe.column, 'pointermove', 1, kind);
                touchAt(safe.row, safe.column, 'pointerup', 1, kind);
                mouseAt(safe.row, safe.column, 'mousedown');
                mouseAt(safe.row, safe.column, 'mouseup');
            }
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
            touchAt(safe.row, safe.column, 'pointerdown', 1, 'mouse');
            mouseAt(safe.row, safe.column, 'mousedown');
            mouseAt(safe.row, safe.column, 'mouseup');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
        });
    });
});
