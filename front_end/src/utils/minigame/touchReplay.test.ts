import { describe, expect, it, vi } from 'vitest';

import { LeftClickTraining, multiTouchModes } from './leftClickTraining';
import { replayFrame } from './replay';
import { decodeTouchEvents, readTouchRecording } from './touchRecording';
import type { TouchRecording, TrainingTouchInput } from './touchRecording';
import { rebuildTouchReplay, TouchReplayRecorder } from './touchReplay';

function input(now: number, pointerId: number, action: TrainingTouchInput['action'], column = 0.5): TrainingTouchInput {
    return { now, pointerId, action, column, row: 0.5, cellSize: 24 };
}

const [, , mode] = multiTouchModes;
const board = Array.from({ length: 8 }, (_row, row) => Array.from({ length: 8 }, () => (row === 0 ? 10 : 16)));

describe('multi-touch recordings', () => {
    it('keeps canonical Expert coordinates when the displayed cell size changes', () => {
        const [expert] = multiTouchModes.filter(({ key, density }) => key === 'e' && density === 87.5);
        const game = new LeftClickTraining(expert);
        const recorder = new TouchReplayRecorder(expert, game.board);
        const safe = game.board.flatMap((row, r) => row.flatMap((cell, c) => (cell === 10 ? [{ row: r, column: c }] : [])));
        let result: ReturnType<TouchReplayRecorder['update']> = null;
        for (const [index, { row, column }] of safe.entries()) {
            const now = 100 + index * 10;
            recorder.capture({ now, pointerId: 1, action: 'down', row: row + 0.5, column: column + 0.5, cellSize: index === 0 ? 21 : 38 });
            game.trigger(row, column, now);
            result = recorder.update(now, game.phase, game.elapsedMs(now));
            if (game.phase === 'playing') recorder.capture({ now, pointerId: 1, action: 'up', row: row + 0.5, column: column + 0.5, cellSize: 38 });
        }
        if (result === null) throw new Error('Missing completed replay');
        const replay = rebuildTouchReplay(expert, result.recording, result.durationMs);
        expect(replay.recording.cellSize).toBe(21);
        expect(replay.snapshots.at(-1)).toMatchObject({ board: game.board, remaining: 0 });
        expect(game.phase).toBe('won');
    });

    it('rebuilds independent concurrent contacts and opens cells only on touch down', () => {
        const game = new LeftClickTraining(mode, undefined, board);
        const recorder = new TouchReplayRecorder(mode, board);
        recorder.capture(input(100, 42, 'down'));
        game.trigger(0, 0, 100);
        expect(recorder.update(100, game.phase, 0)).toBeNull();
        recorder.capture(input(110, 99, 'down', 1.5));
        game.trigger(0, 1, 110);
        recorder.capture(input(115, 42, 'move', 2.5));
        recorder.capture(input(120, 99, 'cancel', 1.5));
        recorder.capture(input(125, 42, 'up', 2.5));
        // Browser IDs may be reused; the archive assigns a new monotonically increasing ID.
        for (let column = 2; column < 8; column++) {
            const now = 100 + column * 20;
            recorder.capture(input(now, 42, 'down', column + 0.5));
            game.trigger(0, column, now);
            if (column < 7) recorder.capture(input(now + 5, 42, 'up', column + 0.5));
        }
        const random = vi.spyOn(Math, 'random').mockImplementation(() => {
            throw new Error('Replay must reuse the initial board');
        });
        try {
            const replay = recorder.update(240, game.phase, game.elapsedMs(240));
            if (replay === null) throw new Error('Missing replay');
            expect(replay.recording.cellSize).toBe(24);
            expect(replay.recording.events.slice(0, 5)).toEqual([
                [0, 12, 12, 0, 0], [10, 24, 0, 1, 0], [5, 24, 0, 0, 1], [5, -24, 0, 1, 3], [5, 24, 0, 0, 2],
            ]);
            expect(replayFrame(replay, { timeMs: 10 }).contacts.map((contact) => contact.id)).toEqual([0, 1]);
            expect(replayFrame(replay, { timeMs: 15 }).remaining).toBe(6);
            expect(replayFrame(replay, { timeMs: 20 }).contacts.map((contact) => contact.id)).toEqual([0]);
            expect(replayFrame(replay, { timeMs: 25 }).contacts).toEqual([]);
            expect(replayFrame(replay, { timeMs: 0, eventIndex: -1 }).board).toEqual(board);
            expect(replayFrame(replay, { timeMs: 0 })).toMatchObject({ remaining: 7, cursor: undefined });
            expect(replayFrame(replay, { timeMs: 99999 })).toMatchObject({ board: game.board, remaining: 0, timeMs: 140 });
            expect(replay.snapshots).toHaveLength(9);
            expect(rebuildTouchReplay(mode, JSON.parse(JSON.stringify(replay.recording)), replay.durationMs)).toEqual(replay);
            const { length } = replay.events;
            recorder.capture(input(9999, 42, 'up'));
            expect(replay.events).toHaveLength(length);
        } finally {
            random.mockRestore();
        }
    });

    it('keeps same-timestamp contacts ordered when seeking and uses 32 for null cell size', () => {
        const recording: TouchRecording = { version: 1, cellSize: null, initialBoard: 'AP////////8', events: [[0, 16, 16, 0, 0], [0, 32, 0, 1, 0], [10, -32, 0, 0, 2]] };
        const replay = rebuildTouchReplay(mode, recording, 10);
        expect(replayFrame(replay, { timeMs: 0 }).remaining).toBe(6);
        expect(replayFrame(replay, { timeMs: 0, eventIndex: 0 }).remaining).toBe(7);
        expect(replayFrame(replay, { timeMs: 10 }).contacts).toEqual([{ id: 1, row: 0.5, column: 1.5 }]);
        expect(replay.events[1].column).toBe(1.5);
    });

    it('rejects broken contact lifetimes, tuples and unsafe deltas', () => {
        const source: TouchRecording = { version: 1, cellSize: 32, initialBoard: 'AP////////8', events: [] };
        for (const events of [
            [[0, 16, 16, 0, 1]], [[0, 16, 16, 1, 0]], [[0, 16, 16, 0, 0], [0, 0, 0, 0, 0]],
            [[0, 16, 16, 0, 0], [0, 0, 0, 0, 2], [0, 0, 0, 0, 1]], [[-1, 0, 0, 0, 0]],
            [[0, 0, 0, 0, 4]], [[0, 0, 0, 0]], [[0, Number.MAX_SAFE_INTEGER + 1, 0, 0, 0]],
        ]) expect(() => readTouchRecording(mode, { ...source, events })).toThrow();
        expect(() => readTouchRecording(mode, { ...source, version: 0 })).toThrow();
        expect(() => readTouchRecording(mode, { ...source, cellSize: 0 })).toThrow();
        expect(decodeTouchEvents(mode, source)).toEqual([]);
    });
});
