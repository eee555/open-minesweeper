export interface ReplayBoardSize {
    rows: number;
    columns: number;
    total?: number;
}

export type EncodedQuestion = [row: number, column: number, mineDirection: number];
export type EncodedTrainingBoard = string | EncodedQuestion[];

// The same row-major neighbor order as FlagChordTraining.
export const mineDirections = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]] as const;

export function requireReplay(condition: boolean, message = 'Invalid minigame recording'): asserts condition {
    if (!condition) throw new Error(message);
}

export function replayInteger(value: unknown): number {
    requireReplay(typeof value === 'number' && Number.isSafeInteger(value), 'Expected a safe replay integer');
    return value;
}

export function replayObject(value: unknown): Record<string, unknown> {
    requireReplay(value !== null && typeof value === 'object' && !Array.isArray(value), 'Expected a replay object');
    return value as Record<string, unknown>;
}

export function readBoard(size: ReplayBoardSize, value: unknown): number[][] {
    requireReplay(Array.isArray(value) && value.length === size.rows, 'Invalid replay board height');
    return value.map((row: unknown) => {
        requireReplay(Array.isArray(row) && row.length === size.columns, 'Invalid replay board width');
        return row.map(replayInteger);
    });
}

/** Row-major cells, packed most significant bit first, using standard unpadded Base64. */
export function encodeMines(size: ReplayBoardSize, value: number[][]): string {
    const board = readBoard(size, value);
    const bytes = new Uint8Array(size.rows * size.columns / 8);
    board.flat().forEach((cell, index) => {
        if (cell === 16) bytes[Math.floor(index / 8)] |= 1 << (7 - index % 8);
    });
    return btoa(String.fromCharCode(...bytes)).replace(/=+$/, '');
}

export function decodeMines(size: ReplayBoardSize, value: unknown): number[][] {
    requireReplay(typeof value === 'string' && value.length === Math.ceil(size.rows * size.columns / 6) && (/^[A-Za-z0-9+/]+$/).test(value), 'Invalid replay mine string');
    const bytes = atob(value + '='.repeat((4 - value.length % 4) % 4));
    requireReplay(bytes.length * 8 === size.rows * size.columns && btoa(bytes).replace(/=+$/, '') === value, 'Invalid replay mine padding');
    return Array.from({ length: size.rows }, (_row, row) => Array.from({ length: size.columns }, (_column, column) => {
        const index = row * size.columns + column;
        return (bytes.charCodeAt(Math.floor(index / 8)) & (1 << (7 - index % 8))) === 0 ? 10 : 16;
    }));
}

export function encodeQuestions(size: ReplayBoardSize, value: number[][]): EncodedQuestion[] {
    const board = readBoard(size, value);
    const questions: EncodedQuestion[] = [];
    board.forEach((cells, row) => {
        cells.forEach((cell, column) => {
            if (cell !== 1) return;
            const directions = mineDirections.flatMap(([dr, dc], index) => (board[row + dr]?.[column + dc] === 16 ? [index] : []));
            requireReplay(directions.length === 1, 'A replay question must have one mine');
            questions.push([row, column, directions[0]]);
        });
    });
    const restored = decodeQuestions(size, questions);
    requireReplay(board.every((cells, row) => cells.every((cell, column) => restored[row][column] === cell)), 'Invalid replay question board');
    return questions;
}

export function decodeQuestions(size: ReplayBoardSize, value: unknown): number[][] {
    requireReplay(Array.isArray(value) && value.length === size.total, 'Invalid replay question count');
    const board = Array.from({ length: size.rows }, () => Array.from({ length: size.columns }, () => 0));
    for (const item of value as unknown[]) {
        requireReplay(Array.isArray(item) && item.length === 3, 'Invalid replay question');
        const [row, column, direction] = item.map(replayInteger);
        requireReplay(row > 0 && column > 0 && row < size.rows - 1 && column < size.columns - 1 && direction >= 0 && direction < 8, 'Invalid replay question position');
        for (let r = row - 1; r <= row + 1; r++) {
            for (let c = column - 1; c <= column + 1; c++) {
                requireReplay(board[r][c] === 0, 'Overlapping replay questions');
                board[r][c] = 10;
            }
        }
        board[row][column] = 1;
        const [dr, dc] = mineDirections[direction];
        board[row + dr][column + dc] = 16;
    }
    return board;
}

export function missingCellBoard(size: ReplayBoardSize, mines: number[][], target: unknown): number[][] {
    requireReplay(Array.isArray(target) && target.length === 2, 'Invalid replay target');
    const [row, column] = target.map(replayInteger);
    requireReplay(row >= 0 && column >= 0 && row < size.rows && column < size.columns && mines[row][column] !== 16, 'Invalid replay target');
    return mines.map((cells, r) => cells.map((cell, c) => {
        if (cell === 16) return 16;
        if (r === row && c === column) return 10;
        return mineDirections.reduce((count, [dr, dc]) => count + Number(mines[r + dr]?.[c + dc] === 16), 0);
    }));
}
