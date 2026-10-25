import { shuffler } from 'd3-array';

import { TrainingClock } from './clock';
import type { TrainingPhase } from './clock';
import { trainingLevels } from './levels';

export { trainingLevels } from './levels';
export type { TrainingPhase } from './clock';
export const trainingDensities = [
    { value: 50, label: '1/2' },
    { value: 75, label: '3/4' },
    { value: 87.5, label: '7/8' },
] as const;

export const leftClickModes = trainingLevels.flatMap((level) => trainingDensities.map(({ value: density }) => ({
    ...level,
    density,
    rankingKey: `left-click-${level.key}-${density}-v1`,
    mines: level.rows * level.columns * density / 100,
    safe: level.rows * level.columns * (100 - density) / 100,
})));
export type LeftClickMode = Omit<typeof leftClickModes[number], 'rows' | 'columns'> & { rows: number; columns: number };
export const multiTouchModes: LeftClickMode[] = leftClickModes.map((mode) => ({ ...mode, rankingKey: mode.rankingKey.replace('left-click-', 'multi-touch-') }));

/** 游戏规则与显示编码分离；时间由触发操作的调用方提供。 */
export class LeftClickTraining {
    public readonly mode: LeftClickMode;
    public phase: TrainingPhase = 'ready';
    private readonly mines: Set<number>;
    private readonly opened = new Set<number>();
    private readonly clock = new TrainingClock();
    private exploded: number | null = null;

    public constructor(mode: LeftClickMode, random: () => number = Math.random, initialBoard?: number[][]) {
        this.mode = mode;
        if (initialBoard === undefined) {
            const indices = Array.from({ length: mode.rows * mode.columns }, (_, i) => i);
            this.mines = new Set(shuffler(random)(indices).slice(0, mode.mines));
        } else {
            this.mines = new Set(initialBoard.flatMap((row, r) => row.flatMap((value, c) => (value === 16 ? [r * mode.columns + c] : []))));
        }
    }

    public get remainingSafe(): number {
        return this.mode.safe - this.opened.size;
    }

    public get board(): number[][] {
        return Array.from({ length: this.mode.rows }, (_row, row) => Array.from({ length: this.mode.columns }, (_column, column) => {
            const index = row * this.mode.columns + column;
            if (index === this.exploded) return 15;
            if (this.mines.has(index)) return 16;
            return this.opened.has(index) ? 0 : 10;
        }));
    }

    public elapsedMs(now: number): number {
        return this.clock.elapsedMs(now);
    }

    /** 调用方决定触发时机：鼠标左键弹起或触屏按下。 */
    public trigger(row: number, column: number, now: number): boolean {
        if (this.phase === 'won' || this.phase === 'lost') return false;
        if (!Number.isInteger(row) || !Number.isInteger(column) || row < 0 || column < 0 || row >= this.mode.rows || column >= this.mode.columns) return false;
        const index = row * this.mode.columns + column;
        if (this.opened.has(index)) return false;
        this.clock.start(now);
        this.phase = 'playing';
        if (this.mines.has(index)) {
            this.exploded = index;
            this.phase = 'lost';
            this.clock.finish(now, false);
        } else {
            this.opened.add(index);
            if (this.remainingSafe === 0) {
                this.phase = 'won';
                this.clock.finish(now, true);
            }
        }
        return true;
    }
}
