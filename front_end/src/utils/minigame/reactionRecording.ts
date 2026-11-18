import { bisector } from 'd3-array';

import { replayInteger, replayObject, requireReplay } from './boardEncoding';
import type { BoardPress } from './boardPress';
import { ReactionTraining } from './reactionTraining';
import type { ReactionMode } from './reactionTraining';
import type { TrainingMouseInput } from './recording';

export interface ReactionRecording {
    version: 1;
    draws: (0 | 1)[];
    sides: (0 | 1)[];
    clicks: [downDelta: number, upDelta: number][];
}

export interface ReactionSample {
    previousUpMs: number;
    downMs: number;
    upMs: number;
    jump: boolean;
}

export interface ReactionFrame {
    timeMs: number;
    board: number[][];
    remaining: number;
    pressed: BoardPress | null;
}

export interface ReactionReplay {
    game: 'reaction';
    mode: ReactionMode;
    recording: ReactionRecording;
    durationMs: number;
    frames: ReactionFrame[];
    samples: ReactionSample[];
}

export function readReactionRecording(value: unknown): ReactionRecording {
    const data = replayObject(value);
    requireReplay(data.version === 1, 'Unsupported reaction recording version');
    const bits = (source: unknown): (0 | 1)[] => {
        requireReplay(Array.isArray(source) && source.length <= 80, 'Invalid reaction bits');
        return source.map((item: unknown) => {
            requireReplay(item === 0 || item === 1, 'Invalid reaction bit');
            return item;
        });
    };
    requireReplay(Array.isArray(data.clicks) && data.clicks.length > 0 && data.clicks.length <= 80, 'Invalid reaction clicks');
    const clicks = data.clicks.map((item: unknown): [number, number] => {
        requireReplay(Array.isArray(item) && item.length === 2, 'Invalid reaction time pair');
        const down = replayInteger(item[0]);
        const up = replayInteger(item[1]);
        requireReplay(down >= 0 && up >= 0, 'Negative reaction time');
        return [down, up];
    });
    requireReplay(clicks[0][0] === 0, 'Invalid first reaction press');
    return { version: 1, draws: bits(data.draws), sides: bits(data.sides), clicks };
}

/** Only time pairs committed by advancing clicks survive; input coordinates are never kept. */
export class ReactionRecorder {
    public readonly game: ReactionTraining;
    private readonly recording: ReactionRecording = { version: 1, draws: [], sides: [], clicks: [] };
    private down: number | null = null;
    private startedAt: number | null = null;
    private lastUp = 0;

    public constructor(mode: ReactionMode, random: () => number = Math.random) {
        this.game = new ReactionTraining(mode.length, mode.probability / 100, mode.target, () => {
            const value = random();
            this.recording.draws.push(value < mode.probability / 100 ? 1 : 0);
            return value;
        });
    }

    public capture(input: Pick<TrainingMouseInput, 'now' | 'action'>): void {
        if (input.action === 'lc') this.down = input.now;
        else if (input.action === null || input.action === 'rc' || input.action === 'rr') this.down = null;
    }

    public trigger(row: number, column: number, now: number): boolean {
        const { down } = this;
        this.down = null;
        if (down === null) return false;
        const first = this.game.nextColumn === null;
        if (!this.game.trigger(row, column, now)) return false;
        this.startedAt ??= now;
        const downMs = Math.round(down - this.startedAt);
        const upMs = Math.round(now - this.startedAt);
        this.recording.clicks.push(this.recording.clicks.length === 0 ? [0, Math.max(0, -downMs)] : [downMs - this.lastUp, upMs - downMs]);
        if (first) this.recording.sides.push(column === 0 ? 0 : 1);
        this.lastUp = upMs;
        return true;
    }

    public finish(): ReactionRecording {
        requireReplay(this.game.phase === 'won', 'Reaction recording is unfinished');
        return readReactionRecording(this.recording);
    }
}

export function rebuildReactionReplay(mode: ReactionMode, source: unknown, scoreMs: number): ReactionReplay {
    const recording = readReactionRecording(source);
    requireReplay(Number.isSafeInteger(scoreMs) && scoreMs > 0, 'Invalid reaction score');
    let drawIndex = 0;
    let sideIndex = 0;
    const game = new ReactionTraining(mode.length, mode.probability / 100, mode.target, () => {
        const draw = recording.draws[drawIndex++];
        requireReplay(draw !== undefined, 'Missing reaction draw');
        return draw === 1 ? 0 : 1;
    });
    const [[, origin]] = recording.clicks;
    const frames: ReactionFrame[] = [{ timeMs: -origin, board: game.board, remaining: mode.target, pressed: null }];
    const samples: ReactionSample[] = [];
    let timeline = 0;
    let previousColumn = 0;
    let previousUpMs = 0;
    for (const [downDelta, upDelta] of recording.clicks) {
        requireReplay(game.phase !== 'won', 'Extra reaction click');
        const downMs = timeline + downDelta - origin;
        timeline += downDelta + upDelta;
        requireReplay(Number.isSafeInteger(timeline), 'Reaction timeline overflow');
        const upMs = timeline - origin;
        const first = game.nextColumn === null;
        let column = game.nextColumn;
        if (first) {
            const side = recording.sides[sideIndex++];
            requireReplay(side !== undefined, 'Missing reaction starting side');
            column = side === 0 ? 0 : mode.length - 1;
        }
        requireReplay(column !== null, 'Missing reaction position');
        frames.push({ timeMs: downMs, board: game.board, remaining: mode.target - game.reactions, pressed: { row: 0, column, chord: false } });
        requireReplay(game.trigger(0, column, upMs), 'Invalid advancing reaction click');
        frames.push({ timeMs: upMs, board: game.board, remaining: mode.target - game.reactions, pressed: null });
        if (!first) samples.push({ previousUpMs, downMs, upMs, jump: Math.abs(column - previousColumn) === 2 });
        previousColumn = column;
        previousUpMs = upMs;
    }
    requireReplay(game.phase === 'won' && game.reactions === mode.target, 'Unfinished reaction recording');
    requireReplay(drawIndex === recording.draws.length && sideIndex === recording.sides.length, 'Extra reaction data');
    requireReplay(Math.max(1, previousUpMs) === scoreMs, 'Reaction score mismatch');
    return { game: 'reaction', mode, recording, durationMs: scoreMs, frames, samples };
}

const frameIndex = bisector((frame: ReactionFrame) => frame.timeMs);
export function reactionFrame(replay: ReactionReplay, timeMs: number): ReactionFrame {
    const time = Math.max(0, Math.min(replay.durationMs, timeMs));
    return { ...replay.frames[Math.max(0, frameIndex.right(replay.frames, time) - 1)], timeMs: time };
}
