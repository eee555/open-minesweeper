import { TrainingClock } from './clock';
import type { TrainingPhase } from './clock';

export const reactionLevels = [
    { key: 'b', length: 5, target: 10 },
    { key: 'i', length: 10, target: 20 },
    { key: 'e', length: 20, target: 40 },
] as const;
export const reactionModes = reactionLevels.flatMap((level) => [25, 50].map((probability) => ({ ...level, probability, rankingKey: `reaction-${level.key}-${probability}-v1` })));
export type ReactionMode = typeof reactionModes[number];

/** Only the next cell is sampled, after the current safe cell has been opened. */
export class ReactionTraining {
    public phase: TrainingPhase = 'ready';
    public reactions = 0;
    public line = 1;
    public readonly length: number;
    public readonly probability: number;
    public readonly target: number;
    private cells: number[];
    private direction = 0;
    private next = -1;
    private readonly clock = new TrainingClock();
    private readonly random: () => number;

    public constructor(length: number, probability: number, target: number, random: () => number = Math.random) {
        if (!Number.isSafeInteger(length) || length < 5) throw new Error('Line length must be an integer of at least 5');
        this.length = length;
        this.probability = probability;
        this.target = target;
        this.random = random;
        this.cells = Array.from({ length }, () => 10);
    }

    public get board(): number[][] {
        return [this.cells.map((cell) => (cell === 16 && this.phase !== 'lost' ? 10 : cell)), Array.from({ length: this.length }, () => 11)];
    }

    public get nextColumn(): number | null {
        return this.direction === 0 ? null : this.next;
    }

    public elapsedMs(now: number): number {
        return this.clock.elapsedMs(now);
    }

    public trigger(row: number, column: number, now: number): boolean {
        if (this.phase === 'won' || this.phase === 'lost') return false;
        if (row === 1 && Number.isInteger(column) && column >= 0 && column < this.length) return false;
        const cell = row === 0 ? this.cells[column] : undefined;
        if (cell !== undefined && cell >= 0 && cell <= 8) return false;
        const first = this.direction === 0;
        if (row !== 0 || !Number.isInteger(column) || (first ? column !== 0 && column !== this.length - 1 : column !== this.next)) {
            this.phase = 'lost';
            this.clock.finish(now, false);
            if (this.cells[column] !== undefined && row === 0) this.cells[column] = 15;
            return false;
        }
        this.clock.start(now);
        this.phase = 'playing';
        if (first) this.direction = column === 0 ? 1 : -1;
        else this.reactions++;

        const ahead = column + this.direction;
        const inside = ahead >= 0 && ahead < this.length;
        // A safe penultimate cell forces a final mine. Adjacent mines never occur.
        if (inside) this.cells[ahead] = ahead === 0 || ahead === this.length - 1 || this.random() < this.probability ? 16 : 10;
        const adjacentMines = [column - 1, column + 1].filter((index) => this.cells[index] === 16).length;
        this.cells[column] = (column === 0 || column === this.length - 1 ? 2 : 3) + adjacentMines;
        if (this.reactions >= this.target) {
            this.phase = 'won';
            this.clock.finish(now, true);
            return true;
        }
        this.next = ahead + (this.cells[ahead] === 16 ? this.direction : 0);
        if (!inside || this.next < 0 || this.next >= this.length) {
            this.cells = Array.from({ length: this.length }, () => 10);
            this.direction = 0;
            this.line++;
        }
        return true;
    }
}
