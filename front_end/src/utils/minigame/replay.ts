import { defaultMouseTraceMarkers, mouseTraceMarkerActions } from '@putianyi888/vue3-minesweeper-board';
import type { MouseTraceMarkers } from '@putianyi888/vue3-minesweeper-board';
import { bisector } from 'd3-array';

import { replayInteger } from './boardEncoding';
import type { BoardPress } from './boardPress';
import type { TrainingPhase } from './clock';
import { FlagChordTraining } from './flagChordTraining';
import { LeftClickTraining } from './leftClickTraining';
import type { LeftClickMode } from './leftClickTraining';
import { decodeRecordingEvents, decodeTrainingBoard, encodeTrainingBoard, readTrainingRecording, recordingActions, referenceCellSize } from './recording';
import type { TrainingContext, TrainingMouseInput, TrainingRecording, TrainingReplayEvent } from './recording';
import type { TouchContact, TouchRecording } from './touchRecording';

export type { TrainingMouseInput, TrainingRecording, TrainingReplayEvent } from './recording';

interface ReplayData {
    durationMs: number;
    initialBoard: number[][];
    events: TrainingReplayEvent[];
    snapshots: ReplaySnapshot[];
    chords: FlagChordTiming[];
}

export type TrainingReplay = TrainingContext & ReplayData & { recording: TrainingRecording };
export type TouchTrainingReplay = { game: 'multi-touch'; mode: LeftClickMode } & ReplayData & { recording: TouchRecording };
export type AnyTrainingReplay = TrainingReplay | TouchTrainingReplay;

interface ReplaySnapshot {
    eventIndex: number;
    board: number[][];
    remaining: number;
}

export interface FlagChordTiming {
    flagMs: number;
    leftMs: number;
    chordMs: number;
    eventIndex: number;
}

export interface ReplayPosition {
    timeMs: number;
    eventIndex?: number;
}

export interface TrainingReplayFrame extends ReplaySnapshot {
    timeMs: number;
    pressed: BoardPress | null;
    cursor: { rowIndex: number; columnIndex: number } | undefined;
    contacts: TouchContact[];
}

export const minigameReplayAppearance = {
    opacity: 0,
    lineWidth: 0.08,
    markers: Object.fromEntries(mouseTraceMarkerActions.map((action) => [action, { ...defaultMouseTraceMarkers[action], size: 0.25 }])) as MouseTraceMarkers,
};

export class TrainingReplayRecorder {
    private startedAt: number | null = null;
    private finished = false;
    private pending: TrainingMouseInput | null = null;
    private previousTime = 0;
    private previousSpecialTime = 0;
    private previousX = 0;
    private previousY = 0;
    private readonly context: TrainingContext;
    private readonly recording: TrainingRecording;

    public constructor(context: TrainingContext, initialBoard: number[][]) {
        this.context = context;
        this.recording = { version: 1, cellSize: null, initialBoard: encodeTrainingBoard(context, initialBoard), events: [], specialEvents: [] };
    }

    public capture(input: TrainingMouseInput): void {
        if (this.finished) return;
        this.pending = input;
        if (this.startedAt === null) return;
        const time = replayInteger(Math.max(0, Math.round(input.now - this.startedAt)));
        if (input.action === null) {
            this.recording.specialEvents.push([time - this.previousSpecialTime, this.recording.events.length, 0]);
            this.previousSpecialTime = time;
            return;
        }
        const size = referenceCellSize(this.recording);
        const x = replayInteger(Math.floor(input.column * size));
        const y = replayInteger(Math.floor(input.row * size));
        this.recording.events.push([time - this.previousTime, x - this.previousX, y - this.previousY, recordingActions.indexOf(input.action)]);
        this.previousTime = time;
        this.previousX = x;
        this.previousY = y;
    }

    public update(now: number, phase: TrainingPhase, durationMs: number): TrainingReplay | null {
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
        return rebuildTrainingReplay(this.context, this.recording, durationMs);
    }
}

function createReplayGame(context: TrainingContext, board: number[][]): LeftClickTraining | FlagChordTraining {
    return context.game === 'left-click' ? new LeftClickTraining(context.mode, Math.random, board) : new FlagChordTraining(context.mode, Math.random, board);
}

function applyEvent(game: LeftClickTraining | FlagChordTraining, event: TrainingReplayEvent): boolean {
    if (event.cancelled || event.trigger === null) return false;
    const row = Math.floor(event.row);
    const column = Math.floor(event.column);
    return game instanceof LeftClickTraining ? event.trigger === 'left' && game.trigger(row, column, event.timeMs) : game.act(event.trigger, row, column, event.timeMs);
}

const eventTime = bisector<TrainingReplayEvent, number>((event) => event.timeMs);
const snapshotIndex = bisector<ReplaySnapshot, number>((snapshot) => snapshot.eventIndex);

/** Expand source data once when opening a replay; derived data stays in memory. */
export function rebuildTrainingReplay(context: TrainingContext, source: unknown, durationMs: number): TrainingReplay {
    const recording = readTrainingRecording(context, source);
    const initialBoard = decodeTrainingBoard(context, recording);
    const events = decodeRecordingEvents(context, recording);
    const game = createReplayGame(context, initialBoard);
    const remaining = () => (game instanceof LeftClickTraining ? game.remainingSafe : game.remaining);
    const snapshots: ReplaySnapshot[] = [{ eventIndex: -1, board: game.board, remaining: remaining() }];
    const chords: FlagChordTiming[] = [];
    const flags = new Map<number, number>();
    let leftMs: number | null = null;
    events.forEach((event, eventIndex) => {
        if (event.cancelled) leftMs = null;
        else if (event.action === 'lc') leftMs = event.timeMs;
        const previousRemaining = remaining();
        if (!applyEvent(game, event)) return;
        const { board } = game;
        snapshots.push({ eventIndex, board, remaining: remaining() });
        if (!(game instanceof FlagChordTraining)) return;
        const row = Math.floor(event.row);
        const column = Math.floor(event.column);
        const question = game.questions.findIndex((item) => Math.abs(item.row - row) <= 1 && Math.abs(item.column - column) <= 1);
        if (event.trigger === 'right' && board[row][column] === 11) flags.set(question, event.timeMs);
        const flagMs = flags.get(question);
        if (game.remaining < previousRemaining && flagMs !== undefined && leftMs !== null && leftMs >= flagMs) chords.push({ flagMs, leftMs, chordMs: event.timeMs, eventIndex });
    });
    return { ...context, recording, initialBoard, events, durationMs, snapshots, chords };
}

export function replayFrame(replay: AnyTrainingReplay, position: ReplayPosition): TrainingReplayFrame {
    const timeMs = Math.max(0, Math.min(replay.durationMs, position.timeMs));
    const eventIndex = position.eventIndex ?? eventTime.right(replay.events, timeMs) - 1;
    const event = replay.events[eventIndex];
    const snapshot = replay.snapshots[Math.max(0, snapshotIndex.right(replay.snapshots, eventIndex) - 1)];
    return {
        ...snapshot,
        timeMs,
        eventIndex,
        pressed: event?.pressed ?? null,
        cursor: replay.game === 'multi-touch' || !event?.positionKnown ? undefined : { rowIndex: event.row, columnIndex: event.column },
        contacts: event?.contacts ?? [],
    };
}
