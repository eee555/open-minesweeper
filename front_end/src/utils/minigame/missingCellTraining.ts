import { shuffler } from 'd3-array';

import { TrainingClock } from './clock';
import type { TrainingPhase } from './clock';
import { trainingLevels } from './levels';

export const missingCellRounds = 10;
export const missingCellModes = trainingLevels.map((level) => ({ ...level, mines: { b: 10, i: 40, e: 99 }[level.key] }));
export type MissingCellMode = typeof missingCellModes[number];

export interface MissingCellRoundResult {
    /** Initial board: 16 marks a hidden mine, and 10 marks the only unopened safe cell. */
    board: number[][];
    timeMs: number;
}

export function reviewMissingCellRound(result: MissingCellRoundResult, completed = false): { board: number[][]; target: { row: number; column: number } | null; timeMs: number } {
    let target: { row: number; column: number } | null = null;
    const board = result.board.map((row, r) => row.map((value, c) => {
        if (value === 10) {
            if (!completed) target = { row: r, column: c };
            else return neighbors(r * row.length + c, result.board.length, row.length).filter((index) => result.board[Math.floor(index / row.length)][index % row.length] === 16).length;
        }
        return value === 16 ? 10 : value;
    }));
    return { board, target, timeMs: result.timeMs };
}

function neighbors(index: number, rows: number, columns: number, radius = 1): number[] {
    const row = Math.floor(index / columns);
    const column = index % columns;
    const cells: number[] = [];
    for (let r = Math.max(0, row - radius); r <= Math.min(rows - 1, row + radius); r++) {
        for (let c = Math.max(0, column - radius); c <= Math.min(columns - 1, column + radius); c++) {
            if (r !== row || c !== column) cells.push(r * columns + c);
        }
    }
    return cells;
}

/** 交换目标格与某个雷后，若所有可见数字仍相同，则该题有歧义。 */
export function isUniqueMissingCell(rows: number, columns: number, mines: ReadonlySet<number>, target: number): boolean {
    if (!Number.isInteger(target) || target < 0 || target >= rows * columns || mines.has(target)) return false;
    const openedNeighbors = (index: number) => neighbors(index, rows, columns).filter((cell) => cell !== target && !mines.has(cell));
    const expected = openedNeighbors(target);
    const candidates = expected.length === 0 ? [...mines] : neighbors(target, rows, columns, 2).filter((cell) => mines.has(cell));
    return !candidates.some((mine) => {
        const actual = openedNeighbors(mine);
        return actual.length === expected.length && actual.every((cell, index) => cell === expected[index]);
    });
}

export function isValidMissingCellTarget(rows: number, columns: number, mines: ReadonlySet<number>, target: number): boolean {
    const besideZero = neighbors(target, rows, columns).some((cell) => !mines.has(cell) && neighbors(cell, rows, columns).every((neighbor) => !mines.has(neighbor)));
    return !besideZero && isUniqueMissingCell(rows, columns, mines, target);
}

interface MissingCellPuzzle {
    readonly mines: ReadonlySet<number>;
    readonly target: number;
    readonly numbers: number[][];
}

function createPuzzle(mode: MissingCellMode, random: () => number): MissingCellPuzzle {
    const shuffle = shuffler(random);
    for (let attempt = 0; attempt < 64; attempt++) {
        const cells = shuffle(Array.from({ length: mode.rows * mode.columns }, (_, index) => index));
        const mines = new Set(cells.slice(0, mode.mines));
        // 安全格已经随机排列；没有合格目标时重抽雷阵，限制次数以避免异常随机源导致无界重试。
        const target = cells.slice(mode.mines).find((cell) => isValidMissingCellTarget(mode.rows, mode.columns, mines, cell));
        if (target === undefined) continue;
        const numbers = Array.from({ length: mode.rows }, () => Array.from({ length: mode.columns }, () => 0));
        for (const mine of mines) {
            for (const cell of neighbors(mine, mode.rows, mode.columns)) numbers[Math.floor(cell / mode.columns)][cell % mode.columns]++;
        }
        return { mines, target, numbers };
    }
    throw new Error('Unable to generate a uniquely solvable missing-cell puzzle');
}

export class MissingCellTraining {
    public readonly mode: MissingCellMode;
    public phase: TrainingPhase = 'ready';
    private readonly random: () => number;
    private readonly clock = new TrainingClock();
    private puzzle: MissingCellPuzzle | null = null;
    private completed = 0;
    private readonly results: MissingCellRoundResult[] = [];
    private exploded: number | null = null;

    public constructor(mode: MissingCellMode, random: () => number = Math.random) {
        this.mode = mode;
        this.random = random;
    }

    public get remaining(): number {
        return missingCellRounds - this.completed;
    }

    public get roundTimesMs(): readonly number[] {
        return this.results.map((result) => result.timeMs);
    }

    public get roundResults(): readonly MissingCellRoundResult[] {
        return this.results.map((result) => ({ ...result, board: result.board.map((row) => [...row]) }));
    }

    public get board(): number[][] {
        const { puzzle } = this;
        if (puzzle === null) return Array.from({ length: this.mode.rows }, () => Array.from({ length: this.mode.columns }, () => 10));
        return puzzle.numbers.map((row, r) => row.map((value, c) => {
            const index = r * this.mode.columns + c;
            if (index === this.exploded) return 15;
            if (puzzle.mines.has(index) || (index === puzzle.target && this.phase !== 'won')) return 10;
            return value;
        }));
    }

    public elapsedMs(now: number): number {
        return this.clock.elapsedMs(now);
    }

    /** 首次左键弹起只开始训练；之后每次命中目标立即换题，十题共用同一个时钟。 */
    public trigger(row: number, column: number, now: number): boolean {
        if (this.phase === 'won' || this.phase === 'lost') return false;
        if (!Number.isInteger(row) || !Number.isInteger(column) || row < 0 || column < 0 || row >= this.mode.rows || column >= this.mode.columns) return false;
        if (this.phase === 'ready') {
            this.puzzle = createPuzzle(this.mode, this.random);
            this.clock.start(now);
            this.phase = 'playing';
            return true;
        }
        const { puzzle } = this;
        if (puzzle === null) return false;
        const index = row * this.mode.columns + column;
        if (index === puzzle.target) {
            const board = puzzle.numbers.map((numbers, r) => numbers.map((value, c) => {
                const cell = r * this.mode.columns + c;
                return cell === puzzle.target ? 10 : puzzle.mines.has(cell) ? 16 : value;
            }));
            if (this.remaining > 1) this.puzzle = createPuzzle(this.mode, this.random);
            this.completed++;
            if (this.remaining === 0) {
                this.phase = 'won';
                this.clock.finish(now, true);
            }
            // 使用累计整数毫秒的差值，让各局用时之和与最终计数器完全一致。
            const timeMs = this.clock.elapsedMs(now) - this.results.reduce((total, result) => total + result.timeMs, 0);
            this.results.push({ board, timeMs });
            return true;
        }
        if (!puzzle.mines.has(index)) return false;
        this.exploded = index;
        this.phase = 'lost';
        this.clock.finish(now, false);
        return true;
    }
}
