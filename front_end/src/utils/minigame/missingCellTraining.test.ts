import { describe, expect, it } from 'vitest';

import { isUniqueMissingCell, isValidMissingCellTarget, missingCellModes, missingCellRounds, MissingCellTraining, reviewMissingCellRound } from './missingCellTraining';
import { missingCellCandidates } from './missingCellTraining.testHelpers';

function display(rows: number, columns: number, mines: ReadonlySet<number>, target: number): number[][] {
    return Array.from({ length: rows }, (_row, r) => Array.from({ length: columns }, (_column, c) => {
        if (mines.has(r * columns + c) || r * columns + c === target) return 10;
        return [...mines].filter((mine) => Math.abs(Math.floor(mine / columns) - r) <= 1 && Math.abs(mine % columns - c) <= 1).length;
    }));
}

function randomSource(): () => number {
    let draw = 0;
    return () => (++draw * 0.61803398875) % 1;
}

describe('missing-cell uniqueness', () => {
    it('agrees with every visible-clue constraint for all 3x3 minefields and safe targets', () => {
        for (let mask = 0; mask < 512; mask++) {
            const mines = new Set(Array.from({ length: 9 }, (_, index) => index).filter((index) => (mask & 2 ** index) !== 0));
            for (let target = 0; target < 9; target++) {
                if (mines.has(target)) continue;
                const candidates = missingCellCandidates(display(3, 3, mines, target));
                expect(isUniqueMissingCell(3, 3, mines, target)).toBe(candidates.length === 1);
            }
        }
    });

    it('rejects the ambiguous corner pair despite opened neighbors', () => {
        const mines = new Set([1, 2, 10, 36, 37, 38, 44, 45, 46, 54]);
        expect(missingCellCandidates(display(8, 8, mines, 0))).toEqual([{ row: 0, column: 0 }, { row: 0, column: 1 }]);
        expect(isUniqueMissingCell(8, 8, mines, 0)).toBe(false);
    });

    it('allows an isolated safe center but rejects an indistinguishable mine farther than two cells away', () => {
        const mines = new Set([9, 10, 11, 17, 19, 25, 26, 27]);
        expect(isUniqueMissingCell(8, 8, mines, 18)).toBe(true);
        for (const cell of [45, 46, 47, 53, 54, 55, 61, 62, 63]) mines.add(cell);
        expect(isUniqueMissingCell(8, 8, mines, 18)).toBe(false);
    });

    it.each([-1, 64, 0.5, NaN, 1])('rejects a nonexistent or mined target (%s)', (target) => {
        expect(isUniqueMissingCell(8, 8, new Set([1]), target)).toBe(false);
    });

    it('excludes targets next to zeroes but allows a zero surrounded by nonzero numbers', () => {
        expect(isUniqueMissingCell(8, 8, new Set([0]), 1)).toBe(true);
        expect(isValidMissingCellTarget(8, 8, new Set([0]), 1)).toBe(false);
        const mines = new Set([0, 1, 2, 3, 10, 12, 25, 29, 42, 44]);
        expect(display(8, 8, mines, -1)[3][3]).toBe(0);
        expect(isValidMissingCellTarget(8, 8, mines, 27)).toBe(true);
    });
});

describe('missing-cell training', () => {
    it.each(missingCellModes)('$key waits for the first action, then generates ten uniquely solvable boards with $mines hidden mines', (mode) => {
        let draw = 0;
        const game = new MissingCellTraining(mode, () => (++draw * 0.61803398875) % 1);
        expect(game.board.flat().every((value) => value === 10)).toBe(true);
        expect(game.remaining).toBe(10);
        expect(game.roundTimesMs).toEqual([]);
        expect(draw).toBe(0);
        expect(game.elapsedMs(99999)).toBe(0);
        expect(game.trigger(0, 0, 1000)).toBe(true);
        expect(game.remaining).toBe(10);
        for (let round = 0; round < missingCellRounds; round++) {
            const { board } = game;
            expect(board).toHaveLength(mode.rows);
            expect(board.every((row) => row.length === mode.columns)).toBe(true);
            expect(board.flat().filter((cell) => cell === 10)).toHaveLength(mode.mines + 1);
            expect(board.flat().every((cell) => (cell >= 0 && cell <= 8) || cell === 10)).toBe(true);
            const candidates = missingCellCandidates(board);
            expect(candidates).toHaveLength(1);
            const [target] = candidates;
            for (let r = Math.max(0, target.row - 1); r <= Math.min(mode.rows - 1, target.row + 1); r++) {
                for (let c = Math.max(0, target.column - 1); c <= Math.min(mode.columns - 1, target.column + 1); c++) expect(board[r][c]).not.toBe(0);
            }
            const mines = new Set(board.flatMap((row, r) => row.flatMap((value, c) => (value === 10 && (r !== target.row || c !== target.column) ? [r * mode.columns + c] : []))));
            expect(board).toEqual(display(mode.rows, mode.columns, mines, target.row * mode.columns + target.column));
            expect(game.phase).toBe('playing');
            expect(game.elapsedMs(1050 + round * 100)).toBe(50 + round * 100);
            expect(game.trigger(target.row, target.column, 1100 + round * 100)).toBe(true);
            expect(game.remaining).toBe(9 - round);
            expect(game.roundTimesMs).toEqual(Array.from({ length: round + 1 }, () => 100));
            const result = game.roundResults[round];
            expect(Object.keys(result).sort()).toEqual(['board', 'timeMs']);
            expect(result.board.flat().filter((cell) => cell === 10)).toHaveLength(1);
            expect(result.board.flat().filter((cell) => cell === 16)).toHaveLength(mode.mines);
            expect(reviewMissingCellRound(result)).toEqual({ board, target, timeMs: 100 });
        }
        expect(game.phase).toBe('won');
        expect(game.elapsedMs(99999)).toBe(1000);
        expect(game.roundTimesMs.reduce((total, time) => total + time, 0)).toBe(game.elapsedMs(99999));
        expect(game.board.flat().filter((cell) => cell === 10)).toHaveLength(mode.mines);
        const final = game.board;
        expect(game.trigger(0, 0, 99999)).toBe(false);
        expect(game.board).toEqual(final);
    });

    it('fails with a bounded number of draws when a repeated random source cannot yield any valid target', () => {
        const [mode] = missingCellModes;
        let draws = 0;
        const game = new MissingCellTraining(mode, () => {
            draws++; return 0;
        });
        expect(() => game.trigger(0, 0, 1000)).toThrow('Unable to generate');
        expect(draws).toBeLessThanOrEqual(64 * mode.rows * mode.columns);
        expect(game.phase).toBe('ready');
        expect(game.elapsedMs(99999)).toBe(0);
    });

    it('ignores invalid coordinates and opened cells without resetting the running clock', () => {
        const game = new MissingCellTraining(missingCellModes[0], randomSource());
        for (const [r, c] of [[-1, 0], [0, -1], [8, 0], [0, 8], [0.5, 0], [NaN, 0]]) expect(game.trigger(r, c, 1000)).toBe(false);
        expect(game.phase).toBe('ready');
        expect(game.elapsedMs(99999)).toBe(0);
        game.trigger(0, 0, 1000);
        const { board } = game;
        board.forEach((row, r) => {
            row.forEach((value, c) => {
                if (value <= 8) expect(game.trigger(r, c, 1500)).toBe(false);
            });
        });
        expect(game.board).toEqual(board);
        expect(game.remaining).toBe(10);
        expect(game.elapsedMs(2000)).toBe(1000);
    });

    it('ends the entire run on a mine and freezes its result', () => {
        const game = new MissingCellTraining(missingCellModes[0], randomSource());
        game.trigger(0, 0, 1000);
        const [target] = missingCellCandidates(game.board);
        game.trigger(target.row, target.column, 1200);
        const [nextTarget] = missingCellCandidates(game.board);
        const mines = game.board.flatMap((row, r) => row.flatMap((value, c) => (value === 10 && (r !== nextTarget.row || c !== nextTarget.column) ? [{ row: r, column: c }] : [])));
        const [mine] = mines;
        game.trigger(mine.row, mine.column, 1750);
        expect(game.phase).toBe('lost');
        expect(game.remaining).toBe(9);
        expect(game.board[mine.row][mine.column]).toBe(15);
        expect(game.board.flat().filter((cell) => cell === 15)).toHaveLength(1);
        expect(game.elapsedMs(99999)).toBe(750);
        expect(game.roundTimesMs).toEqual([200]);
        expect(game.trigger(nextTarget.row, nextTarget.column, 2000)).toBe(false);
    });

    it.each([0, 1234.6])('keeps games and display copies independent and freezes positive integer milliseconds (%s ms)', (duration) => {
        const first = new MissingCellTraining(missingCellModes[0], randomSource());
        const second = new MissingCellTraining(missingCellModes[0], randomSource());
        first.trigger(0, 0, 8000);
        const copy = first.board;
        copy[0][0] = 99;
        expect(first.board[0][0]).not.toBe(99);
        for (let round = 0; round < 10; round++) {
            const [target] = missingCellCandidates(first.board);
            first.trigger(target.row, target.column, round === 9 ? 8000 + duration : 8000);
        }
        expect(first.elapsedMs(99999)).toBe(Math.max(1, Math.round(duration)));
        expect(first.roundTimesMs).toEqual([...Array.from({ length: 9 }, () => 0), Math.max(1, Math.round(duration))]);
        expect(first.roundTimesMs.reduce((total, time) => total + time, 0)).toBe(first.elapsedMs(99999));
        expect(second.phase).toBe('ready');
        expect(second.remaining).toBe(10);
        expect(second.elapsedMs(99999)).toBe(0);
        expect(second.roundTimesMs).toEqual([]);
    });

    it('restores a completed board by revealing its target and keeping mines hidden', () => {
        const result = { board: [[16, 1, 0], [1, 10, 0], [0, 0, 0]], timeMs: 100 };
        expect(reviewMissingCellRound(result, true)).toEqual({ board: [[10, 1, 0], [1, 1, 0], [0, 0, 0]], target: null, timeMs: 100 });
        expect(result.board[1][1]).toBe(10);
        expect(reviewMissingCellRound(result).target).toEqual({ row: 1, column: 1 });
    });

    it('records differences of rounded cumulative times without changing previous snapshots', () => {
        const game = new MissingCellTraining(missingCellModes[0], randomSource());
        game.trigger(0, 0, 1000);
        for (const now of [1001.4, 1002.8, 1004.2]) {
            const previous = game.roundTimesMs;
            const [target] = missingCellCandidates(game.board);
            game.trigger(target.row, target.column, now);
            expect(previous).toHaveLength(game.roundTimesMs.length - 1);
        }
        expect(game.roundTimesMs).toEqual([1, 2, 1]);
        const snapshot = game.roundResults;
        snapshot[0].board[0][0] = 99;
        snapshot[0].timeMs = 999;
        expect(game.roundResults[0].board[0][0]).not.toBe(99);
        expect(reviewMissingCellRound(game.roundResults[0]).target?.row).toBeGreaterThanOrEqual(0);
        expect(game.roundTimesMs).toEqual([1, 2, 1]);
    });
});
