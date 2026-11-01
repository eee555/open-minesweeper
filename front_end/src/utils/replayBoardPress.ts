import { pressedBackground } from './minigame/boardPress';

export function replayPressedBackground(board: readonly (readonly number[])[], mouseState: number, position: { rowIndex: number; columnIndex: number } | null | undefined): boolean[][] | undefined {
    if (mouseState !== 4 && mouseState !== 5 && mouseState !== 6) return undefined;
    if (position == null || !Number.isFinite(position.rowIndex) || !Number.isFinite(position.columnIndex)) return undefined;
    const row = Math.floor(position.rowIndex);
    const column = Math.floor(position.columnIndex);
    if (row < 0 || row >= board.length || column < 0 || column >= board[row].length) return undefined;
    return pressedBackground(board, { row, column, chord: mouseState !== 4 });
}
