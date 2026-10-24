import type { Counter } from '@putianyi888/vue3-minesweeper-board';
import { defineComponent, h } from 'vue';

import App from './App.vue';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import type ReplayAnalysis from '@/components/MiniGame/ReplayAnalysis.vue';
import i18n from '@/i18n';
import { rebuildTrainingReplay, replayFrame } from '@/utils/minigame/replay';
import type { TrainingReplay } from '@/utils/minigame/replay';
import { chordAt, isolateMinigameHistory, mouseAt, rightAt, savedMinigameResults } from '@cy/support/minigame';

function mountGame() {
    return cy.mount(defineComponent({ expose: [], render: () => h(App) }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
        const game = wrapper.findComponent(App);
        return cy.wrap(game).as('vue').then(() => ({ wrapper: game }));
    });
}

function questions(board: number[][]) {
    return board.flatMap((row, r) => row.flatMap((value, c) => {
        if (value !== 1) return [];
        const mines: { row: number; column: number }[] = [];
        const safe: { row: number; column: number }[] = [];
        for (let rr = r - 1; rr <= r + 1; rr++) {
            for (let cc = c - 1; cc <= c + 1; cc++) {
                if (rr === r && cc === c) continue;
                if (board[rr][cc] === 16) mines.push({ row: rr, column: cc });
                else safe.push({ row: rr, column: cc });
            }
        }
        return [{ row: r, column: c, value, mines, safe }];
    }));
}

function checkQuestions(total: number, size: number) {
    cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
        const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
        expect(board).to.have.length(size);
        expect(board.every((row) => row.length === size)).to.eq(true);
        const all = questions(board);
        expect(all).to.have.length(total);
        expect(board.flat().filter((value) => value === 2)).to.have.length(0);
        for (const question of all) {
            expect(question.mines).to.have.length(1);
            expect(question.safe).to.have.length(7);
        }
    });
}

describe('flag-and-chord training', () => {
    isolateMinigameHistory();
    it('ignores left clicks, times the first right press, accepts 1.5-click and completes all questions', () => {
        mountGame();
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const all = questions(board);
            const [first] = all;
            const [mine] = first.mines;
            expect(wrapper.findComponent<typeof Counter>('[data-cy="flag-chord-time"]').props()).to.include({ fixed: 3, digits: 3 });
            mouseAt(mine.row, mine.column, 'mousedown');
            mouseAt(mine.row, mine.column, 'mouseup');
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'ready');
            mouseAt(mine.row, mine.column, 'mousedown', 2, 2);
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'playing');
            mouseAt(first.row, first.column, 'mousedown', 0, 3);
            mouseAt(first.row, first.column, 'mouseup', 0, 2);
            mouseAt(first.row, first.column, 'mouseup', 2, 0);
            cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '003');
            for (const question of all.slice(1)) {
                for (const cell of question.mines) rightAt(cell.row, cell.column);
                chordAt(question.row, question.column);
            }
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'won');
            cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '000');
            cy.get('[data-cy="minigame-speed-plot"] .plot-axis--vertical').should('not.exist');
            cy.get<ComponentWrapper<typeof App>>('@vue').then((current) => {
                const replay: TrainingReplay = current.findComponent<typeof ReplayAnalysis>('[data-cy="minigame-replay-analysis"]').props('replay');
                expect(replay.chords).to.have.length(4);
                cy.get('[data-cy="minigame-chord-bars"]').scrollIntoView();
                cy.get('[data-cy="minigame-chord-bars"] .plot-bar rect').first().then(($bar) => {
                    const rect = $bar[0].getBoundingClientRect();
                    cy.get('[data-cy="minigame-chord-bars"]').trigger('pointermove', { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 });
                });
                cy.get('.minigame-speed-marker').should('exist');
                cy.get('[data-cy="flag-chord-time"]').should('have.attr', 'aria-label', (replay.chords[0].chordMs / 1000).toFixed(3).padStart(7, '0'));
                cy.get('[data-tippy-root]').should('contain.text', 'Last flag').and('contain.text', 'Chord trigger');
                cy.get('[data-cy="minigame-chord-bars"]').trigger('pointerleave');
                cy.get('.minigame-speed-marker').should('not.exist');
                cy.get('[data-cy="flag-chord-time"]').should('have.attr', 'aria-label', (replay.durationMs / 1000).toFixed(3).padStart(7, '0'));
            });
            cy.get('[data-cy="flag-chord-time"]').then(($time) => {
                const result = $time.attr('aria-label');
                if (result === undefined) throw new Error('Timer has no accessible value');
                rightAt(mine.row, mine.column);
                cy.get('[data-cy="flag-chord-time"]').should('have.attr', 'aria-label', result);
            });
        });
        savedMinigameResults().then((entries) => {
            expect(entries).to.have.length(1);
            const [entry] = entries;
            if (entry.game !== 'flag-chord') throw new Error('Wrong saved game');
            expect(entry.mode).to.include({ key: 'b', total: 4 });
            expect(Object.keys(entry.replay).sort()).to.deep.eq(['cellSize', 'events', 'initialBoard', 'specialEvents', 'version']);
            const replay = rebuildTrainingReplay(entry, entry.replay, entry.scoreMs);
            expect(replay.chords).to.have.length(4);
            expect(replayFrame(replay, { timeMs: entry.scoreMs }).remaining).to.eq(0);
            cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
                expect(wrapper.emitted('completed')).to.deep.eq([['flag-chord-b-v1', entry.scoreMs, entry.replay]]);
            });
        });
    });

    it('allows wrong flags to be cancelled but loses on a matching, incorrect chord', () => {
        mountGame();
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const [question] = questions(board);
            const [safe] = question.safe;
            rightAt(safe.row, safe.column);
            rightAt(safe.row, safe.column);
            chordAt(question.row, question.column);
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '004');
            rightAt(safe.row, safe.column);
            chordAt(question.row, question.column);
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'lost');
            cy.get<ComponentWrapper<typeof App>>('@vue').should((current) => {
                const replay: TrainingReplay = current.findComponent<typeof ReplayAnalysis>('[data-cy="minigame-replay-analysis"]').props('replay');
                expect(replay.chords).to.have.length(0);
            });
            cy.get('.training-frame-counters').click();
            cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'ready');
            cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '004');
            cy.get('[data-cy="flag-chord-time"]').should('have.attr', 'aria-label', '000.000');
        });
        savedMinigameResults().should('have.length', 0);
        cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
            expect(wrapper.emitted('completed')).to.eq(undefined);
        });
    });

    it('offers two fixed levels and resets the round when switching them', () => {
        mountGame();
        cy.get('[data-cy="flag-chord-level"] input').should(($inputs) => {
            expect(Array.from($inputs, (input) => (input as HTMLInputElement).value)).to.deep.eq(['b', 'i']);
        });
        cy.get('[data-cy="flag-chord-game"] input[type="number"]').should('not.exist');
        cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '004');
        checkQuestions(4, 8);
        cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
            const [question] = questions(wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board'));
            rightAt(question.mines[0].row, question.mines[0].column);
        });
        cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'playing');
        cy.get('[data-cy="flag-chord-level"] input[value="i"]').parent().click();
        cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '015');
        cy.get('[data-cy="flag-chord-time"]').should('have.attr', 'aria-label', '000.000');
        cy.get('[data-cy="flag-chord-game"]').should('have.attr', 'data-phase', 'ready');
        checkQuestions(15, 16);
        cy.get('[data-cy="flag-chord-level"] input[value="b"]').parent().click();
        cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '004');
        checkQuestions(4, 8);
        savedMinigameResults().should('have.length', 0);
    });
});
