import { describe, expect, it } from 'vitest';

import { decodeMines, decodeQuestions, encodeMines, encodeQuestions, mineDirections } from './boardEncoding';
import { flagChordModes, FlagChordTraining } from './flagChordTraining';
import { leftClickModes, LeftClickTraining } from './leftClickTraining';
import { trainingLevels } from './levels';
import { missingCellModes, MissingCellTraining } from './missingCellTraining';
import { missingCellCandidates } from './missingCellTraining.testHelpers';
import { decodeMissingCellRounds, decodeRecordingEvents, readMissingCellRecording, readTrainingRecording } from './recording';
import type { TrainingRecording } from './recording';
import { rebuildTrainingReplay, TrainingReplayRecorder } from './replay';

const context = { game: 'left-click' as const, mode: leftClickModes[0] };
const board = Array.from({ length: 8 }, (_, row) => Array.from({ length: 8 }, () => (row < 4 ? 10 : 16)));
const ordinary: TrainingRecording['events'] = [[0, 16, 16, 2], [10, 32, 0, 1], [15, -3, 2, 0], [0, 0, 0, 2]];
function recording(): TrainingRecording {
    return { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: structuredClone(ordinary), specialEvents: [] };
}

describe('minigame recording format v1', () => {
    it.each(trainingLevels)('packs all cells for $key using standard Base64, including row boundaries and zero padding', (size) => {
        const source = Array.from({ length: size.rows }, (_row, row) => Array.from({ length: size.columns }, (_column, column) => ((row * size.columns + column) % 7 === 0 ? 16 : 10)));
        const encoded = encodeMines(size, source);
        expect(encoded).toHaveLength(Math.ceil(size.rows * size.columns / 6));
        expect(decodeMines(size, encoded)).toEqual(source);
        expect(() => decodeMines(size, encoded + '=')).toThrow();
        expect(() => decodeMines(size, encoded.slice(1))).toThrow();
        if (size.rows * size.columns % 6 !== 0) {
            const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
            const last = alphabet.indexOf(encoded.at(-1) ?? '');
            expect(() => decodeMines(size, encoded.slice(0, -1) + alphabet[last + 1])).toThrow('padding');
        }
    });

    it('keeps the fixed Base64 bit order and all eight question directions', () => {
        const sample = board.map((row) => row.map(() => 10));
        for (const index of [0, 2, 5, 63]) sample[Math.floor(index / 8)][index % 8] = 16;
        expect(encodeMines(trainingLevels[0], sample)).toBe('pAAAAAAAAAE');
        for (let direction = 0; direction < 8; direction++) {
            const questions = [[1, 1, direction], [1, 5, direction], [5, 1, direction], [5, 5, direction]];
            const decoded = decodeQuestions(flagChordModes[0], questions);
            const [dr, dc] = mineDirections[direction];
            expect(decoded[1 + dr][1 + dc]).toBe(16);
            expect(encodeQuestions(flagChordModes[0], decoded)).toEqual(questions);
        }
        expect(() => decodeQuestions(flagChordModes[0], [[1, 1, 0], [1, 2, 0], [5, 1, 0], [5, 5, 0]])).toThrow('Overlapping');
        expect(() => decodeQuestions(flagChordModes[0], [[0, 1, 0], [1, 5, 0], [5, 1, 0], [5, 5, 0]])).toThrow();
    });

    it('migrates unversioned or explicit v0 events into independent ordinary and special timelines', () => {
        const legacy = { initialBoard: board,
            events: [
                { timeMs: 0, row: 0.5, column: 0.5, action: 'lr' },
                { timeMs: 10, row: 0.5, column: 1.5, action: 'lc' },
                { timeMs: 25, row: 0.5625, column: 1.40625, action: 'mv' },
                { timeMs: 25, cancelled: true },
                { timeMs: 25, row: 0.5625, column: 1.40625, action: 'lr' },
                { timeMs: 30, cancelled: true },
            ] };
        const migrated = readTrainingRecording(context, legacy);
        expect(migrated).toEqual({ ...recording(), cellSize: null, specialEvents: [[25, 3, 0], [5, 4, 0]] });
        expect(readTrainingRecording(context, { ...legacy, version: 0 })).toEqual(migrated);
        expect(readTrainingRecording(context, migrated)).toEqual(migrated);
        const events = decodeRecordingEvents(context, migrated);
        expect(events.map((event) => event.timeMs)).toEqual([0, 10, 25, 25, 25, 30]);
        expect(events.filter((event) => event.trigger === 'left')).toHaveLength(1);
        expect(rebuildTrainingReplay(context, migrated, 30).snapshots).toHaveLength(2);
    });

    it('uses insertion indices to distinguish same-millisecond reset positions and handles repeated resets', () => {
        const beforeRelease = { ...recording(), specialEvents: [[25, 3, 0], [0, 3, 0]] as TrainingRecording['specialEvents'] };
        expect(decodeRecordingEvents(context, beforeRelease).filter((event) => event.trigger === 'left')).toHaveLength(1);
        const afterRelease = { ...recording(), specialEvents: [[25, 4, 0]] as TrainingRecording['specialEvents'] };
        expect(decodeRecordingEvents(context, afterRelease).filter((event) => event.trigger === 'left')).toHaveLength(2);
        const beforeFirst = { ...recording(), specialEvents: [[0, 0, 0]] as TrainingRecording['specialEvents'] };
        expect(decodeRecordingEvents(context, beforeFirst)[0]).toMatchObject({ cancelled: true, positionKnown: false });
        for (const specialEvents of [[[1, 0, 0]], [[0, 5, 0]], [[26, 3, 0]], [[25, 4, 0], [0, 3, 0]], [[0, 0, 1]]]) {
            expect(() => readTrainingRecording(context, { ...recording(), specialEvents })).toThrow();
        }
    });

    it('fixes the pixel reference when timing starts and keeps it across display-size changes', () => {
        const recorder = new TrainingReplayRecorder(context, board);
        recorder.capture({ now: 0, action: 'lc', row: 0.5, column: 0.5, cellSize: 16 });
        recorder.capture({ now: 10, action: 'lr', row: 0.5, column: 0.5, cellSize: 48 });
        recorder.update(10, 'playing', 0);
        recorder.capture({ now: 20, action: 'mv', row: 1, column: 1.25, cellSize: 16 });
        const replay = recorder.update(20, 'lost', 10);
        expect(replay?.recording).toMatchObject({ cellSize: 48, events: [[0, 24, 24, 2], [10, 36, 24, 0]] });
        expect(replay?.events[1]).toMatchObject({ row: 1, column: 1.25 });
        expect(decodeRecordingEvents(context, { ...recording(), cellSize: null })).toEqual(decodeRecordingEvents(context, recording()));
    });

    it('retains signed outside-board deltas, pixel floors and coordinates wider than 32 bits', () => {
        const source = { ...recording(), events: [[0, 31, 16, 2], [1, -32, 2 ** 40, 0]] as TrainingRecording['events'] };
        const decoded = decodeRecordingEvents(context, source);
        expect(decoded[0].column).toBe(31 / 32);
        expect(decoded[1]).toMatchObject({ column: -1 / 32, row: (16 + 2 ** 40) / 32, pressed: null, trigger: null });
        for (const version of [null, true, '1', -1, 2, undefined]) {
            expect(() => readTrainingRecording(context, { ...source, version })).toThrow();
        }
        expect(() => readTrainingRecording(context, { ...source, cellSize: undefined })).toThrow();
        expect(() => readTrainingRecording(context, { ...source, events: [[0, Number.MAX_SAFE_INTEGER, 0, 0], [1, 1, 0, 0]] })).toThrow();
    });

    it.each(flagChordModes)('round-trips actual flag-and-chord boards for $key', (mode) => {
        const game = new FlagChordTraining(mode, () => 0.37);
        const source = { initialBoard: game.board, events: [] };
        const flagContext = { game: 'flag-chord' as const, mode };
        const migrated = readTrainingRecording(flagContext, source);
        expect(migrated.initialBoard).toHaveLength(mode.total);
        expect(rebuildTrainingReplay(flagContext, migrated, 1).initialBoard).toEqual(game.board);
    });

    it('migrates and reviews all ten missing cell boards without persisting numbers', () => {
        let draw = 0;
        const game = new MissingCellTraining(missingCellModes[0], () => (++draw * 0.61803398875) % 1);
        game.trigger(0, 0, 0);
        for (let index = 0; index < 10; index++) {
            const [target] = missingCellCandidates(game.board);
            game.trigger(target.row, target.column, (index + 1) * 100);
        }
        const source = { rounds: game.roundResults };
        const migrated = readMissingCellRecording(game.mode, source);
        expect(migrated.version).toBe(1);
        expect(migrated.rounds.every((round) => round.board.length === 11 && round.target.length === 2)).toBe(true);
        expect(decodeMissingCellRounds(game.mode, migrated)).toEqual(game.roundResults);
        expect(readMissingCellRecording(game.mode, migrated)).toEqual(migrated);
        const invalid = structuredClone(migrated);
        const [mine] = game.roundResults[0].board.flatMap((cells, row) => cells.flatMap((cell, column) => (cell === 16 ? [[row, column] as [number, number]] : [])));
        invalid.rounds[0].target = mine;
        expect(() => readMissingCellRecording(game.mode, invalid)).toThrow('target');
    });

    it('stores no random seed and reconstructs the initial left-click board', () => {
        const game = new LeftClickTraining(leftClickModes[2], () => 0.37);
        const leftContext = { game: 'left-click' as const, mode: game.mode };
        const source = readTrainingRecording(leftContext, { initialBoard: game.board, events: [] });
        expect(rebuildTrainingReplay(leftContext, source, 1).initialBoard).toEqual(game.board);
    });
});
