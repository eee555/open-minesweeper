import { describe, expect, it } from 'vitest';

import { replayPressedBackground } from './replayBoardPress';

const board = [[10, 10, 10, 10], [10, 11, 10, 10], [0, 1, 10, 10], [10, 10, 10, 10]];

describe('replay pressed background', () => {
    it('presses only the cursor cell for state 4 without changing board data', () => {
        const original = structuredClone(board);
        expect(replayPressedBackground(board, 4, { rowIndex: 1.8, columnIndex: 2.1 })).toEqual([
            [false, false, false, false], [false, false, true, false], [true, true, false, false], [false, false, false, false],
        ]);
        expect(board).toEqual(original);
        expect(replayPressedBackground(board, 4, { rowIndex: 1, columnIndex: 1 })?.[1][1]).toBe(false);
    });

    it.each([5, 6])('presses a clipped 3x3 area except flags for state %s', (state) => {
        expect(replayPressedBackground(board, state, { rowIndex: 1.5, columnIndex: 1.5 })).toEqual([
            [true, true, true, false], [true, false, true, false], [true, true, true, false], [false, false, false, false],
        ]);
        expect(replayPressedBackground(board, state, { rowIndex: 0, columnIndex: 0 })).toEqual([
            [true, true, false, false], [true, false, false, false], [true, true, false, false], [false, false, false, false],
        ]);
    });

    it.each([0, 1, 2, 3, 7, 8])('uses the natural background for state %s', (state) => {
        expect(replayPressedBackground(board, state, { rowIndex: 1, columnIndex: 2 })).toBeUndefined();
    });

    it.each([null, undefined, { rowIndex: NaN, columnIndex: 1 }, { rowIndex: 1, columnIndex: Infinity }, { rowIndex: -0.1, columnIndex: 1 }, { rowIndex: 1, columnIndex: 4 }, { rowIndex: 4, columnIndex: 1 }])('ignores invalid cursor position %j', (position) => {
        expect(replayPressedBackground(board, 5, position)).toBeUndefined();
    });
});
