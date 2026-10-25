import type { MouseTraceEvent } from '@putianyi888/vue3-minesweeper-board';

import { ClassicMouseAutomaton } from '../classicMouse';
import type { ClassicMouseAction, ClassicMouseEvent } from '../classicMouse';

import { decodeMines, decodeQuestions, encodeMines, encodeQuestions, missingCellBoard, readBoard, replayInteger, replayObject, requireReplay } from './boardEncoding';
import type { EncodedTrainingBoard, ReplayBoardSize } from './boardEncoding';
import type { BoardPress } from './boardPress';
import type { FlagChordMode } from './flagChordTraining';
import type { LeftClickMode } from './leftClickTraining';
import { missingCellRounds } from './missingCellTraining';
import type { MissingCellRoundResult } from './missingCellTraining';
import type { TouchContact, TouchRecording } from './touchRecording';

export const defaultReplayCellSize = 32;
export const recordingActions = ['mv', 'lc', 'lr', 'rc', 'rr'] as const;
export type TrainingContext = { game: 'left-click'; mode: LeftClickMode } | { game: 'flag-chord'; mode: FlagChordMode };
export type MouseRecordingEvent = [dt: number, x: number, y: number, action: number];
export type SpecialRecordingEvent = [dt: number, index: number, type: number];

/** Input coordinates remain in cell units until the recorder fixes its pixel reference. */
export interface TrainingMouseInput {
    now: number;
    action: ClassicMouseEvent | null;
    row: number;
    column: number;
    cellSize: number;
}

export interface TrainingReplayEvent extends MouseTraceEvent {
    timeMs: number;
    pressed: BoardPress | null;
    trigger: ClassicMouseAction | null;
    cancelled: boolean;
    positionKnown: boolean;

    /** Present only in multi-touch replays; each contact has an independent path. */
    touchId?: number;
    contacts?: TouchContact[];
}

export interface TrainingRecording {
    version: 1;
    cellSize: number | null;
    initialBoard: EncodedTrainingBoard;
    events: MouseRecordingEvent[];
    specialEvents: SpecialRecordingEvent[];
}

export interface MissingCellRecording {
    version: 1;
    rounds: { board: string; target: [number, number]; timeMs: number }[];
}

export type MinigameReplayData = TrainingRecording | TouchRecording | MissingCellRecording;

export function recordingVersion(value: unknown): 0 | 1 {
    const data = replayObject(value);
    const version = Object.hasOwn(data, 'version') ? replayInteger(data.version) : 0;
    requireReplay(version === 0 || version === 1, 'Unsupported minigame replay version');
    return version;
}

export function referenceCellSize(recording: Pick<TrainingRecording, 'cellSize'>): number {
    if (recording.cellSize === null) return defaultReplayCellSize;
    const size = replayInteger(recording.cellSize);
    requireReplay(size > 0, 'Invalid replay cell size');
    return size;
}

export function encodeTrainingBoard(context: TrainingContext, board: number[][]): EncodedTrainingBoard {
    return context.game === 'left-click' ? encodeMines(context.mode, board) : encodeQuestions(context.mode, board);
}

export function decodeTrainingBoard(context: TrainingContext, recording: TrainingRecording): number[][] {
    return context.game === 'left-click' ? decodeMines(context.mode, recording.initialBoard) : decodeQuestions(context.mode, recording.initialBoard);
}

function nonnegative(value: unknown): number {
    const integer = replayInteger(value);
    requireReplay(integer >= 0, 'Negative replay timestamp or index');
    return integer;
}

/** v0 lacks a version field. Conversion does not persist runtime flags or previews. */
export function readTrainingRecording(context: TrainingContext, value: unknown): TrainingRecording {
    const data = replayObject(value);
    if (recordingVersion(data) === 1) {
        referenceCellSize(data as unknown as TrainingRecording);
        requireReplay(Array.isArray(data.events) && Array.isArray(data.specialEvents), 'Missing replay event arrays');
        const recording = { version: 1 as const, cellSize: data.cellSize as number | null, initialBoard: data.initialBoard as EncodedTrainingBoard, events: data.events as MouseRecordingEvent[], specialEvents: data.specialEvents as SpecialRecordingEvent[] };
        decodeTrainingBoard(context, recording);
        decodeRecordingEvents(context, recording);
        return recording;
    }
    const board = readBoard(context.mode, data.initialBoard);
    if (context.game === 'left-click') requireReplay(board.every((row) => row.every((cell) => cell === 10 || cell === 16)), 'Invalid legacy left-click board');
    const recording: TrainingRecording = { version: 1, cellSize: null, initialBoard: encodeTrainingBoard(context, board), events: [], specialEvents: [] };
    requireReplay(Array.isArray(data.events), 'Missing legacy replay events');
    let previousTime = 0;
    let previousSpecialTime = 0;
    let previousX = 0;
    let previousY = 0;
    for (const item of data.events as unknown[]) {
        const event = replayObject(item);
        const time = nonnegative(event.timeMs);
        if (event.cancelled === true) {
            recording.specialEvents.push([time - previousSpecialTime, recording.events.length, 0]);
            previousSpecialTime = time;
            continue;
        }
        requireReplay(typeof event.column === 'number' && Number.isFinite(event.column) && typeof event.row === 'number' && Number.isFinite(event.row), 'Invalid legacy mouse coordinates');
        const x = replayInteger(Math.floor(event.column * defaultReplayCellSize));
        const y = replayInteger(Math.floor(event.row * defaultReplayCellSize));
        const action = recordingActions.findIndex((candidate) => candidate === event.action);
        requireReplay(action >= 0, 'Invalid legacy mouse action');
        recording.events.push([time - previousTime, x - previousX, y - previousY, action]);
        previousTime = time;
        previousX = x;
        previousY = y;
    }
    decodeRecordingEvents(context, recording);
    return recording;
}

/** Expand both timelines in insertion order; all game state is derived by the automaton. */
export function decodeRecordingEvents(context: TrainingContext, recording: TrainingRecording): TrainingReplayEvent[] {
    const size = referenceCellSize(recording);
    let timeMs = 0;
    let x = 0;
    let y = 0;
    const ordinary = recording.events.map((value) => {
        requireReplay(Array.isArray(value) && value.length === 4, 'Invalid replay mouse tuple');
        const [dt, dx, dy, action] = value.map(replayInteger);
        requireReplay(dt >= 0 && action >= 0 && action < recordingActions.length, 'Invalid replay mouse event');
        timeMs = replayInteger(timeMs + dt);
        x = replayInteger(x + dx);
        y = replayInteger(y + dy);
        return { timeMs, row: y / size, column: x / size, action: recordingActions[action] };
    });
    let specialTime = 0;
    let previousIndex = 0;
    const special = recording.specialEvents.map((value) => {
        requireReplay(Array.isArray(value) && value.length === 3, 'Invalid replay special tuple');
        const [dt, index, type] = value.map(nonnegative);
        specialTime = replayInteger(specialTime + dt);
        requireReplay(type === 0 && index >= previousIndex && index <= ordinary.length, 'Invalid replay insertion index or special type');
        requireReplay((index === 0 || ordinary[index - 1].timeMs <= specialTime) && (index === ordinary.length || specialTime <= ordinary[index].timeMs), 'Conflicting replay event order');
        previousIndex = index;
        return { timeMs: specialTime, index };
    });
    const mouse = new ClassicMouseAutomaton();
    if (context.game === 'left-click') mouse.step('lc');
    const events: TrainingReplayEvent[] = [];
    let specialIndex = 0;
    for (let index = 0; index <= ordinary.length; index++) {
        while (special[specialIndex]?.index === index) {
            const event = special[specialIndex++];
            mouse.reset();
            const previous = ordinary[index - 1];
            events.push({ timeMs: event.timeMs, row: previous?.row ?? 0, column: previous?.column ?? 0, action: 'mv', state: 'uu', pressed: null, trigger: null, cancelled: true, positionKnown: previous !== undefined });
        }
        const event = ordinary[index];
        if (event === undefined) continue;
        const intent = mouse.step(event.action);
        const row = Math.floor(event.row);
        const column = Math.floor(event.column);
        const inside = row >= 0 && column >= 0 && row < context.mode.rows && column < context.mode.columns;
        const state = mouse.state === 'both-down' ? 'dd' : mouse.state === 'left-down' || mouse.state === 'chord-left-down' ? 'du' : mouse.state === 'right-down' || mouse.state === 'chord-right-down' ? 'ud' : 'uu';
        const pressed = inside && (mouse.state === 'left-down' || mouse.state === 'both-down') ? { row, column, chord: mouse.state === 'both-down' } : null;
        events.push({ ...event, state, pressed, trigger: inside ? intent : null, cancelled: false, positionKnown: true });
    }
    return events;
}

export function encodeMissingCellRecording(size: ReplayBoardSize, rounds: readonly MissingCellRoundResult[]): MissingCellRecording {
    requireReplay(rounds.length === missingCellRounds, 'Invalid replay round count');
    return { version: 1,
        rounds: rounds.map((round) => {
            const board = readBoard(size, round.board);
            const targets = board.flatMap((cells, row) => cells.flatMap((cell, column) => (cell === 10 ? [[row, column] as [number, number]] : [])));
            requireReplay(targets.length === 1, 'Missing cell replay must have one target');
            const timeMs = nonnegative(round.timeMs);
            const encoded = encodeMines(size, board);
            const restored = missingCellBoard(size, decodeMines(size, encoded), targets[0]);
            requireReplay(board.every((cells, row) => cells.every((cell, column) => restored[row][column] === cell)), 'Invalid legacy missing cell board');
            return { board: encoded, target: targets[0], timeMs };
        }) };
}

export function readMissingCellRecording(size: ReplayBoardSize, value: unknown): MissingCellRecording {
    const data = replayObject(value);
    const version = recordingVersion(data);
    requireReplay(Array.isArray(data.rounds) && data.rounds.length === missingCellRounds, 'Invalid replay round count');
    if (version === 0) {
        return encodeMissingCellRecording(size, data.rounds.map((item: unknown) => {
            const round = replayObject(item);
            return { board: readBoard(size, round.board), timeMs: nonnegative(round.timeMs) };
        }));
    }
    const rounds = data.rounds.map((item: unknown) => {
        const round = replayObject(item);
        const board = decodeMines(size, round.board);
        missingCellBoard(size, board, round.target);
        return { board: round.board as string, target: (round.target as [number, number]).slice() as [number, number], timeMs: nonnegative(round.timeMs) };
    });
    return { version: 1, rounds };
}

export function decodeMissingCellRounds(size: ReplayBoardSize, value: unknown): MissingCellRoundResult[] {
    const recording = readMissingCellRecording(size, value);
    return recording.rounds.map((round) => ({ board: missingCellBoard(size, decodeMines(size, round.board), round.target), timeMs: round.timeMs }));
}
