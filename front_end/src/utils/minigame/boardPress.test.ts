import { describe, expect, it } from 'vitest';

import { pressedBackground } from './boardPress';

describe('shared board press preview', () => {
    it('presses 3x3 backgrounds except flags, preserving foregrounds and game data', () => {
        const board = Array.from({ length: 5 }, () => Array.from({ length: 5 }, () => 10));
        board[1][1] = 16;
        board[2][1] = 11;
        board[2][2] = 2;
        const original = board.map((row) => [...row]);
        const background = pressedBackground(board, { row: 2, column: 2, chord: true });
        expect(background).toEqual(Array.from({ length: 5 }, (_row, r) => Array.from({ length: 5 }, (_column, c) => r >= 1 && r <= 3 && c >= 1 && c <= 3 && !(r === 2 && c === 1))));
        expect(board).toEqual(original);
        expect(pressedBackground(board, null)).toBeUndefined();
        expect(pressedBackground(board, null, true)).toEqual([
            [false, false, false, false, false], [false, true, false, false, false], [false, false, true, false, false], [false, false, false, false, false], [false, false, false, false, false],
        ]);
        expect(pressedBackground(board, { row: 2, column: 1, chord: false }, true)?.[2][1]).toBe(false);
        expect(board).toEqual(original);
    });

    it('clips at corners and follows the current cursor cell', () => {
        const board = Array.from({ length: 4 }, () => [10, 10, 10, 10]);
        expect(pressedBackground(board, { row: 0, column: 0, chord: true })).toEqual([
            [true, true, false, false], [true, true, false, false], [false, false, false, false], [false, false, false, false],
        ]);
        expect(pressedBackground(board, { row: 3, column: 3, chord: true })).toEqual([
            [false, false, false, false], [false, false, false, false], [false, false, true, true], [false, false, true, true],
        ]);
    });

    it('keeps a single left press local and preserves natural down cells elsewhere', () => {
        const board = [[10, 16, 11], [0, 2, 10], [14, 15, 18]];
        expect(pressedBackground(board, { row: 0, column: 0, chord: false })).toEqual([[true, false, false], [true, true, false], [true, true, true]]);
        expect(pressedBackground(board, { row: 0, column: 1, chord: false })).toEqual([[false, true, false], [true, true, false], [true, true, true]]);
        expect(pressedBackground(board, { row: 0, column: 2, chord: false })?.[0][2]).toBe(false);
        expect(pressedBackground([[12, 13, 17, 11]], { row: 0, column: 2, chord: false })).toEqual([[false, false, true, false]]);
    });
});
