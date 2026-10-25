import { decodeMines, encodeMines, replayInteger } from './boardEncoding';
import type { TrainingPhase } from './clock';
import { LeftClickTraining } from './leftClickTraining';
import type { LeftClickMode } from './leftClickTraining';
import { referenceCellSize } from './recording';
import type { TouchTrainingReplay } from './replay';
import { decodeTouchEvents, readTouchRecording, touchActions } from './touchRecording';
import type { TouchRecording, TrainingTouchInput } from './touchRecording';

export function rebuildTouchReplay(mode: LeftClickMode, source: unknown, durationMs: number): TouchTrainingReplay {
    const recording = readTouchRecording(mode, source);
    const events = decodeTouchEvents(mode, recording);
    const board = decodeMines(mode, recording.initialBoard);
    const game = new LeftClickTraining(mode, undefined, board);
    const snapshots: TouchTrainingReplay['snapshots'] = [{ eventIndex: -1, board: game.board, remaining: game.remainingSafe }];
    events.forEach((event, eventIndex) => {
        if (event.trigger === 'left' && game.trigger(Math.floor(event.row), Math.floor(event.column), event.timeMs)) {
            snapshots.push({ eventIndex, board: game.board, remaining: game.remainingSafe });
        }
    });
    return { game: 'multi-touch', mode, initialBoard: board, recording, events, durationMs, snapshots, chords: [] };
}

export class TouchReplayRecorder {
    private startedAt: number | null = null;
    private finished = false;
    private pending: TrainingTouchInput | null = null;
    private previousTime = 0;
    private previousX = 0;
    private previousY = 0;
    private nextId = 0;
    private readonly contacts = new Map<number, number>();
    private readonly recording: TouchRecording;
    private readonly mode: LeftClickMode;

    public constructor(mode: LeftClickMode, initialBoard: number[][]) {
        this.mode = mode;
        this.recording = { version: 1, cellSize: null, initialBoard: encodeMines(mode, initialBoard), events: [] };
    }

    public capture(input: TrainingTouchInput): void {
        if (this.finished) return;
        this.pending = input;
        if (this.startedAt === null) return;
        if (input.action === 'down') this.contacts.set(input.pointerId, this.nextId++);
        const id = this.contacts.get(input.pointerId);
        if (id === undefined) return;
        const time = replayInteger(Math.max(0, Math.round(input.now - this.startedAt)));
        const size = referenceCellSize(this.recording);
        const x = replayInteger(Math.floor(input.column * size));
        const y = replayInteger(Math.floor(input.row * size));
        this.recording.events.push([time - this.previousTime, x - this.previousX, y - this.previousY, id, touchActions.indexOf(input.action)]);
        this.previousTime = time;
        this.previousX = x;
        this.previousY = y;
        if (input.action === 'up' || input.action === 'cancel') this.contacts.delete(input.pointerId);
    }

    public update(now: number, phase: TrainingPhase, durationMs: number): TouchTrainingReplay | null {
        if (this.finished || phase === 'ready') return null;
        if (this.startedAt === null) {
            this.startedAt = now;
            if (this.pending !== null) {
                this.recording.cellSize = this.pending.cellSize;
                this.capture({ ...this.pending, now });
            }
        }
        if (phase === 'playing') return null;
        this.finished = true;
        return rebuildTouchReplay(this.mode, this.recording, durationMs);
    }
}
