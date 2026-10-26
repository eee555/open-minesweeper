import type { Counter } from '@putianyi888/vue3-minesweeper-board';
import { defineComponent, h } from 'vue';

import App from './App.vue';
import type TrainingResults from './Results.vue';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import i18n from '@/i18n';
import { offlineDownloadFilename } from '@/utils/minigame/games';
import { reviewMissingCellRound } from '@/utils/minigame/missingCellTraining';
import { missingCellCandidates } from '@/utils/minigame/missingCellTraining.testHelpers';
import { decodeMissingCellRounds } from '@/utils/minigame/recording';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { chordAt, isolateMinigameHistory, mouseAt, rightAt, savedMinigameResults } from '@cy/support/minigame';

function mountGame() {
    return cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
        const game = wrapper.findComponent(App);
        return cy.wrap(game).as('vue').then(() => ({ wrapper: game }));
    });
}

describe('missing cell training', () => {
    isolateMinigameHistory();
    beforeEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });

    it('starts only on release and completes ten boards with a shared timer', () => {
        const snapshots: { board: number[][]; target: { row: number; column: number } }[] = [];
        let times: readonly number[] = [];
        mountGame();
        cy.get('[data-cy="missing-cell-download"]').should('have.attr', 'download', offlineDownloadFilename);
        rightAt(0, 0);
        chordAt(0, 0);
        mouseAt(0, 0, 'mousedown');
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', '000.000');
        mouseAt(0, 0, 'mouseup');
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', '010');
        for (let round = 0; round < 10; round++) {
            cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                const candidates = missingCellCandidates(board);
                expect(candidates).to.have.length(1);
                const [target] = candidates;
                snapshots.push({ board, target });
                expect(board.flat().filter((cell) => cell === 10)).to.have.length(11);
                for (let r = Math.max(0, target.row - 1); r <= Math.min(7, target.row + 1); r++) {
                    for (let c = Math.max(0, target.column - 1); c <= Math.min(7, target.column + 1); c++) expect(board[r][c]).not.to.eq(0);
                }
                expect(wrapper.findComponent<typeof Counter>('[data-cy="missing-cell-time"]').props()).to.include({ fixed: 3, digits: 3, size: 32 });
                mouseAt(target.row, target.column, 'mousedown');
                cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', String(10 - round).padStart(3, '0'));
                mouseAt(target.row, target.column, 'mouseup');
                cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', String(9 - round).padStart(3, '0'));
                cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', round === 9 ? 'won' : 'playing');
            });
        }
        cy.get('[data-cy="missing-cell-time"]').then(($time) => {
            const result = $time.attr('aria-label');
            if (result === undefined) throw new Error('Timer has no accessible value');
            mouseAt(0, 0, 'mousedown');
            mouseAt(0, 0, 'mouseup');
            cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', result);
            cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                times = wrapper.findComponent<typeof TrainingResults>('[data-cy="missing-cell-results"]').props('timesMs');
                expect(times).to.have.length(10);
                expect((times.reduce((total, time) => total + time, 0) / 1000).toFixed(3).padStart(7, '0')).to.eq(result);
            });
            for (const index of [0, 9]) {
                if (index === 0) {
                    cy.get('[data-cy="missing-cell-round-times"]').scrollIntoView();
                    cy.get('[data-cy="missing-cell-round-times"] .plot-bar rect').eq(index).should('be.visible').then(($bar) => {
                        const rect = $bar[0].getBoundingClientRect();
                        // Keep viewport coordinates valid after measuring the rendered bar.
                        cy.get('[data-cy="missing-cell-round-times"]').trigger('pointermove', { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2, scrollBehavior: false });
                    });
                } else {
                    cy.clock();
                    cy.get('[data-cy="missing-cell-time-stack"] [data-cy="Board 10"]').trigger('mouseenter');
                    cy.tick(300);
                    cy.get('[id^="tippy-"]').should('not.exist');
                }
                cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', String(10 - index).padStart(3, '0'));
                cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                    const preview = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]');
                    expect(preview.props('board')).to.deep.eq(snapshots[index].board);
                    expect(preview.props('highlight')).to.deep.eq(snapshots[index].target);
                    cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', (times[index] / 1000).toFixed(3).padStart(7, '0'));
                });
                cy.get('[data-cy="minigame-board-highlight"]').should('be.visible');
                if (index === 0) cy.get('[data-cy="missing-cell-round-times"]').trigger('pointerleave');
                else cy.get('[data-cy="missing-cell-time-stack"] [data-cy="Board 10"]').trigger('mouseleave');
                cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', '000');
                cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', result);
                cy.get('[data-cy="minigame-board-highlight"]').should('not.exist');
                cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                    const finalBoard: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                    expect(finalBoard.flat().filter((cell) => cell === 10)).to.have.length(10);
                });
            }
        });
        cy.get('[data-cy="missing-cell-round-times"] .plot-bar rect').should('have.length', 10);
        cy.get('[data-cy="missing-cell-time-stack"] [data-cy^="Board "]').should('have.length', 10);
        cy.get('[data-cy="missing-cell-results"]').within(() => {
            cy.get('figcaption, .dot').should('not.exist');
            cy.get('.plot-axis').should('have.length', 1);
            cy.get('.plot-axis text').should('not.exist');
            cy.get('.plot-axis line').should('have.length', 1);
        });
        cy.get('[data-cy="missing-cell-results"]').should(($results) => {
            const [results] = $results;
            const board = results.parentElement?.querySelector('.training-scroll');
            if (board === null || board === undefined) throw new Error('Missing board scroll container');
            expect(results.getBoundingClientRect().top).to.be.at.least(board.getBoundingClientRect().bottom);
        });
        cy.get('.training-frame-counters').click();
        cy.get('[data-cy="missing-cell-results"]').should('not.exist');
        savedMinigameResults().then((entries) => {
            expect(entries).to.have.length(1);
            const [entry] = entries;
            if (entry.game !== 'missing-cell') throw new Error('Wrong saved game');
            expect(entry.mode.key).to.eq('b');
            expect(entry.version).to.eq(1);
            expect(entry.rounds.every((result) => Object.keys(result).sort().join() === 'board,target,timeMs')).to.eq(true);
            expect(decodeMissingCellRounds(entry.mode, entry).map((result) => {
                const { board, target } = reviewMissingCellRound(result);
                return { board, target };
            })).to.deep.eq(snapshots);
            expect(entry.rounds.map((round) => round.timeMs)).to.deep.eq(times);
            expect(entry.scoreMs).to.eq(times.reduce((total, time) => total + time, 0));
            cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
                expect(wrapper.emitted('completed')).to.deep.eq([['missing-cell-b-v1', entry.scoreMs, { version: 1, rounds: entry.rounds }]]);
            });
        });
    });

    it('ignores open cells, right clicks and chords, loses on a mine and restarts from the counter bar', () => {
        mountGame();
        mouseAt(0, 0, 'mousedown');
        mouseAt(0, 0, 'mouseup');
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const [target] = missingCellCandidates(board);
            const [mine] = board.flatMap((row, r) => row.flatMap((value, c) => (value === 10 && (r !== target.row || c !== target.column) ? [{ row: r, column: c }] : [])));
            const [opened] = board.flatMap((row, r) => row.flatMap((value, c) => (value <= 8 ? [{ row: r, column: c }] : [])));
            rightAt(target.row, target.column);
            chordAt(target.row, target.column);
            mouseAt(opened.row, opened.column, 'mousedown');
            mouseAt(opened.row, opened.column, 'mouseup');
            cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', '010');
            cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
            mouseAt(mine.row, mine.column, 'mousedown');
            mouseAt(mine.row, mine.column, 'mouseup');
            cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'lost');
            cy.get('.training-frame-counters').click();
            cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', '000.000');
            cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', '010');
        });
        savedMinigameResults().should('have.length', 0);
        cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
            expect(wrapper.emitted('completed')).to.eq(undefined);
        });
    });

    it('resets when switching level and uses classic mine counts', () => {
        mountGame();
        for (const [level, columns, mines] of [['i', 16, 40], ['e', 30, 99]] as const) {
            cy.get(`[data-cy="missing-cell-level"] input[value="${level}"]`).parent().click();
            cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy="missing-cell-time"]').should('have.attr', 'aria-label', '000.000');
            mouseAt(0, 0, 'mousedown');
            mouseAt(0, 0, 'mouseup');
            cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
                const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                expect(board).to.have.length(16);
                expect(board.every((row) => row.length === columns)).to.eq(true);
                expect(board.flat().filter((cell) => cell === 10)).to.have.length(mines + 1);
                expect(missingCellCandidates(board)).to.have.length(1);
            });
        }
        savedMinigameResults().should('have.length', 0);
    });
});
