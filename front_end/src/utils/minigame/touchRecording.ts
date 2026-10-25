import { decodeMines, replayInteger, replayObject, requireReplay } from './boardEncoding';
import type { LeftClickMode } from './leftClickTraining';
import { recordingVersion, referenceCellSize } from './recording';
import type { TrainingReplayEvent } from './recording';

export const touchActions = ['down', 'move', 'up', 'cancel'] as const;
export type TouchAction = typeof touchActions[number];
export type TouchRecordingEvent = [dt: number, dx: number, dy: number, contact: number, action: number];

export interface TouchRecording {
    version: 1;
    cellSize: number | null;
    initialBoard: string;
    events: TouchRecordingEvent[];
}

export interface TouchContact {
    id: number;
    row: number;
    column: number;
}

export interface TrainingTouchInput {
    now: number;
    pointerId: number;
    action: TouchAction;
    row: number;
    column: number;
    cellSize: number;
}

/** Coordinates and time use one global delta stream, including interleaved contacts. */
export function decodeTouchEvents(mode: LeftClickMode, recording: TouchRecording): TrainingReplayEvent[] {
    const size = referenceCellSize(recording);
    const active = new Map<number, TouchContact>();
    let timeMs = 0;
    let x = 0;
    let y = 0;
    let nextId = 0;
    return recording.events.map<TrainingReplayEvent>((value) => {
        requireReplay(Array.isArray(value) && value.length === 5, 'Invalid replay touch tuple');
        const [dt, dx, dy, id, action] = value.map(replayInteger);
        requireReplay(dt >= 0 && id >= 0 && action >= 0 && action < touchActions.length, 'Invalid replay touch event');
        timeMs = replayInteger(timeMs + dt);
        x = replayInteger(x + dx);
        y = replayInteger(y + dy);
        const row = y / size;
        const column = x / size;
        if (action === 0) {
            requireReplay(id === nextId, 'Invalid replay contact sequence');
            nextId++;
        } else {
            requireReplay(active.has(id), 'Inactive replay contact');
        }
        if (action < 2) active.set(id, { id, row, column });
        else active.delete(id);
        const inside = row >= 0 && column >= 0 && row < mode.rows && column < mode.columns;
        return {
            timeMs,
            row,
            column,
            touchId: id,
            action: action === 0 ? 'lc' : action === 1 ? 'mv' : 'lr',
            state: action < 2 ? 'du' : 'uu',
            trigger: action === 0 && inside ? 'left' : null,
            pressed: null,
            cancelled: action === 3,
            positionKnown: true,
            contacts: [...active.values()],
        };
    });
}

export function readTouchRecording(mode: LeftClickMode, value: unknown): TouchRecording {
    const data = replayObject(value);
    requireReplay(recordingVersion(data) === 1, 'Multi-touch replays require version 1');
    referenceCellSize(data as unknown as TouchRecording);
    decodeMines(mode, data.initialBoard);
    requireReplay(Array.isArray(data.events), 'Missing replay touch events');
    const recording: TouchRecording = { version: 1, cellSize: data.cellSize as number | null, initialBoard: data.initialBoard as string, events: data.events as TouchRecordingEvent[] };
    decodeTouchEvents(mode, recording);
    return recording;
}
