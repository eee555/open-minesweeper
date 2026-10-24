
import type { BoardBackground, Counter } from '@putianyi888/vue3-minesweeper-board';
import { defineComponent, h } from 'vue';

import minigameVersion from '../../../../local-minigame/version.json';

import App from './App.vue';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import type ReplayAnalysis from '@/components/MiniGame/ReplayAnalysis.vue';
import i18n from '@/i18n';
import { rebuildTrainingReplay, replayFrame } from '@/utils/minigame/replay';
import type { TrainingReplay } from '@/utils/minigame/replay';
import { leftClickDurations, replaySpeeds } from '@/utils/minigame/replayAnalysis';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { isolateMinigameHistory, mouseAt, savedMinigameResults } from '@cy/support/minigame';

function mountGame() {
    return cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
        const game = wrapper.findComponent(App);
        return cy.wrap(game).as('vue').then(() => ({ wrapper: game }));
    });
}

function cells(board: number[][], value: number) {
    return board.flatMap((row, r) => row.flatMap((cell, c) => (cell === value ? [{ row: r, column: c }] : [])));
}

describe('left-click training preview', () => {
    isolateMinigameHistory();
    beforeEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });

    it('offers the versioned offline package download', () => {
        mountGame();
        const filename = `OpenMinesweeperMinigames-${minigameVersion.version}.zip`;
        cy.get('[data-cy="training-download"]').should('be.visible').and('have.attr', 'download', filename).
            and('have.attr', 'href', `${import.meta.env.BASE_URL}assets/${filename}`);
    });

    it('aligns the remaining and time counters with the board at every cell size', () => {
        mountGame();
        for (const size of [16, 24, 32, 40]) {
            cy.then(() => {
                minigameSettings.value.cellSize = size;
            });
            cy.get('.training-frame').should(($frame) => {
                const [frame] = $frame;
                const bar = frame.querySelector('.training-frame-counters');
                const board = frame.querySelector('[data-cy="minigame-board"]');
                const remaining = frame.querySelector('[data-cy="training-remaining"]');
                const time = frame.querySelector('[data-cy="training-time"]');
                if (bar === null || board === null || remaining === null || time === null) throw new Error('Missing board or counters');
                const barRect = bar.getBoundingClientRect();
                const boardRect = board.getBoundingClientRect();
                const remainingRect = remaining.getBoundingClientRect();
                const timeRect = time.getBoundingClientRect();
                const scrollRect = frame.parentElement?.getBoundingClientRect();
                if (scrollRect === undefined) throw new Error('Missing board scroll container');
                const frameRect = frame.getBoundingClientRect();
                expect(frameRect.left + frameRect.width / 2).to.be.closeTo(scrollRect.left + scrollRect.width / 2, 0.5);
                expect(boardRect.width).to.be.closeTo(8 * size, 0.5);
                expect(remainingRect.left).to.be.closeTo(boardRect.left, 0.5);
                expect(timeRect.right).to.be.closeTo(boardRect.right, 0.5);
                expect(remainingRect.right).to.be.at.most(timeRect.left);
                expect(barRect.bottom).to.be.lessThan(boardRect.top);
                expect(barRect.width).to.be.closeTo(boardRect.width + 6, 0.5);
            });
        }
    });

    it('keeps both edges of a wide board reachable in a narrow window', () => {
        cy.viewport(360, 800);
        mountGame();
        cy.get('[data-cy="training-level"] input[value="e"]').parent().click();
        cy.get('.training-scroll').should(($scroll) => {
            const [scroll] = $scroll;
            const frame = scroll.querySelector('.training-frame');
            if (frame === null) throw new Error('Missing board frame');
            expect(scroll.scrollWidth).to.be.greaterThan(scroll.clientWidth);
            expect(frame.getBoundingClientRect().left).to.be.closeTo(scroll.getBoundingClientRect().left, 0.5);
        }).scrollTo('right');
        cy.get('.training-scroll').should(($scroll) => {
            const [scroll] = $scroll;
            const frame = scroll.querySelector('.training-frame');
            if (frame === null) throw new Error('Missing board frame');
            expect(frame.getBoundingClientRect().right).to.be.closeTo(scroll.getBoundingClientRect().right, 0.5);
        });
    });

    it('starts a new round from either counter or the space between them', () => {
        mountGame();
        for (const target of ['remaining', 'time', 'gap']) {
            cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                const board = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                const [safe] = cells(board, 10);
                mouseAt(safe.row, safe.column, 'mousedown');
                mouseAt(safe.row, safe.column, 'mouseup');
                cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
                if (target === 'gap') {
                    cy.get('.training-frame-counters').then(($bar) => {
                        const [bar] = $bar;
                        const remaining = bar.querySelector('[data-cy="training-remaining"]');
                        const time = bar.querySelector('[data-cy="training-time"]');
                        if (remaining === null || time === null) throw new Error('Missing counters');
                        const barRect = bar.getBoundingClientRect();
                        const x = (remaining.getBoundingClientRect().right + time.getBoundingClientRect().left) / 2 - barRect.left;
                        cy.wrap($bar).click(x, barRect.height / 2);
                    });
                } else cy.get(`[data-cy="training-${target}"]`).click();
                cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
                cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '032');
                cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
            });
        }
    });

    it('waits for release, uses release coordinates, ignores right/chord and cancels on blur', () => {
        mountGame().then(({ wrapper }) => {
            const board = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const timer = wrapper.findComponent<typeof Counter>('[data-cy="training-time"]');
            expect(timer.props()).to.include({ value: 0, fixed: 3, digits: 3, size: 32 });
            const [first, second] = cells(board, 10);
            cy.get('[data-cy="training-density"] option').should(($options) => {
                expect(Array.from($options, (option) => option.textContent)).to.deep.eq(['1/2', '3/4', '7/8']);
            });
            mouseAt(first.row, first.column, 'mousedown');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '032');
            mouseAt(second.row, second.column, 'mouseup');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            mouseAt(first.row, first.column, 'mousedown', 2, 2);
            mouseAt(first.row, first.column, 'mouseup', 2, 0);
            mouseAt(first.row, first.column, 'mousedown');
            mouseAt(first.row, first.column, 'mousedown', 2, 3);
            mouseAt(first.row, first.column, 'mouseup', 2, 1);
            mouseAt(first.row, first.column, 'mouseup');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            mouseAt(first.row, first.column, 'mousedown');
            cy.window().trigger('blur');
            mouseAt(first.row, first.column, 'mouseup');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            mouseAt(first.row, first.column, 'mousedown');
            cy.window().then((win) => win.dispatchEvent(new MouseEvent('mouseup', { button: 0, buttons: 0, clientX: -1, clientY: -1 })));
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            cy.get('.training-frame-counters').click();
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
        });
    });

    it('wins after all safe cells, freezes its result, and generates the selected mode', () => {
        mountGame();
        cy.get('[data-cy="training-density"]').select('87.5');
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '008');
        cy.get('[data-cy="minigame-board"]').then(() => {
            cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                const board = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                const safe = cells(board, 10);
                const [mine] = cells(board, 16);
                safe.forEach(({ row, column }) => {
                    mouseAt(row, column, 'mousedown');
                    mouseAt(row, column, 'mouseup');
                });
                cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'won');
                cy.get('[data-cy="training-time"]').then(($time) => {
                    const result = $time.attr('aria-label');
                    if (result === undefined) throw new Error('Timer has no accessible value');
                    mouseAt(mine.row, mine.column, 'mousedown');
                    mouseAt(mine.row, mine.column, 'mouseup');
                    cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', result);
                });
                cy.get('[data-cy="minigame-replay-controls"]').should('be.visible');
                cy.get('[data-cy="minigame-speed-plot"] .minigame-speed-axis-left').should('exist');
                cy.get('[data-cy="minigame-speed-plot"] .minigame-speed-axis-right').should('exist');
                cy.get<ComponentWrapper<typeof App>>('@vue').should((current) => {
                    const replay: TrainingReplay = current.findComponent<typeof ReplayAnalysis>('[data-cy="minigame-replay-analysis"]').props('replay');
                    expect(leftClickDurations(replay)).to.have.length(7);
                });
                cy.get<ComponentWrapper<typeof App>>('@vue').then((current) => {
                    const replay: TrainingReplay = current.findComponent<typeof ReplayAnalysis>('[data-cy="minigame-replay-analysis"]').props('replay');
                    const samples = replaySpeeds(replay);
                    const sample = samples[Math.floor(samples.length / 2)];
                    cy.get('[data-cy="minigame-speed-plot"]').scrollIntoView();
                    cy.get('[data-cy="minigame-speed-plot"]').then(($plot) => {
                        const rect = $plot[0].getBoundingClientRect();
                        cy.wrap($plot).trigger('pointermove', { clientX: rect.left + 48 + (rect.width - 96) * sample.timeMs / replay.durationMs, clientY: rect.top + 60 });
                    });
                    cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', (sample.timeMs / 1000).toFixed(3).padStart(7, '0'));
                    cy.get<ComponentWrapper<typeof App>>('@vue').should((hovered) => {
                        expect(hovered.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('cursorPosition')).to.deep.eq(replayFrame(replay, { timeMs: sample.timeMs }).cursor);
                    });
                    cy.get('[data-tippy-root]').should('contain.text', 'Mouse speed').and('contain.text', 'Click speed');
                    cy.get('[data-cy="minigame-speed-plot"]').trigger('pointerleave');
                    cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', (replay.durationMs / 1000).toFixed(3).padStart(7, '0'));
                });
                cy.get('[data-cy="minigame-replay-position"]').invoke('val', '0').trigger('input');
                cy.get('[data-cy="minigame-replay-position"]').trigger('change');
                cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '007');
                cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
                cy.get('[data-cy="training-level"] input[value="e"]').parent().click();
                cy.get('[data-cy="minigame-replay-controls"]').should('not.exist');
                cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '060');
                cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
                cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
                cy.get<ComponentWrapper<typeof App>>('@vue').should((current) => {
                    const updatedBoard: number[][] = current.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                    expect(updatedBoard).to.have.length(16);
                    expect(updatedBoard.every((row) => row.length === 30)).to.eq(true);
                    expect(cells(updatedBoard, 16)).to.have.length(420);
                });
            });
        });
        savedMinigameResults().then((entries) => {
            expect(entries).to.have.length(1);
            const [entry] = entries;
            if (entry.game !== 'left-click') throw new Error('Wrong saved game');
            expect(entry.mode).to.include({ key: 'b', density: 87.5 });
            expect(entry.replay.events).not.to.have.length(0);
            expect(Object.keys(entry.replay).sort()).to.deep.eq(['cellSize', 'events', 'initialBoard', 'specialEvents', 'version']);
            const replay = rebuildTrainingReplay(entry, entry.replay, entry.scoreMs);
            expect(replayFrame(replay, { timeMs: entry.scoreMs }).remaining).to.eq(0);
            cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
                expect(wrapper.emitted('completed')).to.deep.eq([[entry.mode.rankingKey, entry.scoreMs, entry.replay]]);
            });
        });
    });

    it('loses on a mine and blocks subsequent safe clicks', () => {
        mountGame().then(({ wrapper }) => {
            const board = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const [mine] = cells(board, 16);
            const [safe] = cells(board, 10);
            cy.get('.minigame-board-foreground').should('have.css', 'opacity', '0.5');
            mouseAt(mine.row, mine.column, 'mousedown');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get<ComponentWrapper<typeof App>>('@vue').should((current) => {
                const background = current.findComponent<typeof BoardBackground>('.minigame-board-background').props('board');
                expect(background?.[mine.row][mine.column]).to.eq(true);
                expect(background?.[safe.row][safe.column]).to.eq(false);
            });
            mouseAt(mine.row, mine.column, 'mouseup');
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'lost');
            cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
            cy.get<ComponentWrapper<typeof App>>('@vue').should((current) => {
                expect(current.findComponent<typeof BoardBackground>('.minigame-board-background').props('board')).to.eq(undefined);
            });
            mouseAt(safe.row, safe.column, 'mousedown');
            mouseAt(safe.row, safe.column, 'mouseup');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '032');
        });
        savedMinigameResults().should('have.length', 0);
        cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
            expect(wrapper.emitted('completed')).to.eq(undefined);
        });
    });
});
