import 'fake-indexeddb/auto';

import { deleteDB, openDB } from 'idb';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { watch } from 'vue';

import { loadReplayArchiveCodec } from './archive';
import { flagChordModes, FlagChordTraining } from './flagChordTraining';
import type { MinigameResult } from './history';
import { leftClickModes, LeftClickTraining, multiTouchModes } from './leftClickTraining';
import { missingCellModes, MissingCellTraining, reviewMissingCellRound } from './missingCellTraining';
import { missingCellCandidates } from './missingCellTraining.testHelpers';
import { decodeMissingCellRounds, encodeMissingCellRecording } from './recording';
import { rebuildTrainingReplay, replayFrame, TrainingReplayRecorder } from './replay';
import type { TrainingMouseInput, TrainingReplay } from './replay';
import type { TouchRecordingEvent } from './touchRecording';
import { rebuildTouchReplay } from './touchReplay';

const databaseName = 'saolei-minigame';

function input(now: number, row: number, column: number, action: TrainingMouseInput['action']): TrainingMouseInput {
    return { now, row: row + 0.5, column: column + 0.5, action, cellSize: 32 };
}

function leftClickResult(): Extract<MinigameResult, { game: 'left-click' }> {
    const game = new LeftClickTraining(leftClickModes[2], () => 0.37);
    const recorder = new TrainingReplayRecorder({ game: 'left-click', mode: game.mode }, game.board);
    const safe = game.board.flatMap((row, r) => row.flatMap((value, c) => (value === 10 ? [{ row: r, column: c }] : [])));
    let replay: TrainingReplay | null = null;
    for (const [index, { row, column }] of safe.entries()) {
        const now = 100 + index * 50;
        recorder.capture(input(now - 10, row, column, 'lc'));
        recorder.capture(input(now, row, column, 'lr'));
        game.trigger(row, column, now);
        replay = recorder.update(now, game.phase, game.elapsedMs(now));
    }
    if (replay === null) throw new Error('Missing completed left-click replay');
    return { game: 'left-click', mode: game.mode, scoreMs: game.elapsedMs(99999), replay: replay.recording };
}

function flagChordResult(): Extract<MinigameResult, { game: 'flag-chord' }> {
    const game = new FlagChordTraining(flagChordModes[0], () => 0.37);
    const recorder = new TrainingReplayRecorder({ game: 'flag-chord', mode: game.mode }, game.board);
    let replay: TrainingReplay | null = null;
    for (const [index, question] of game.questions.entries()) {
        const now = 100 + index * 100;
        const row = Math.floor(question.mine / game.mode.columns);
        const column = question.mine % game.mode.columns;
        recorder.capture(input(now, row, column, 'rc'));
        game.act('right', row, column, now);
        recorder.update(now, game.phase, game.elapsedMs(now));
        recorder.capture(input(now + 20, question.row, question.column, 'lc'));
        recorder.capture(input(now + 40, question.row, question.column, 'lr'));
        game.act('chord', question.row, question.column, now + 40);
        replay = recorder.update(now + 40, game.phase, game.elapsedMs(now + 40));
        recorder.capture(input(now + 45, question.row, question.column, 'rr'));
    }
    if (replay === null) throw new Error('Missing completed flag-and-chord replay');
    return { game: 'flag-chord', mode: game.mode, scoreMs: game.elapsedMs(99999), replay: replay.recording };
}

function missingCellResult(): Extract<MinigameResult, { game: 'missing-cell' }> {
    let draw = 0;
    const game = new MissingCellTraining(missingCellModes[0], () => (++draw * 0.61803398875) % 1);
    game.trigger(0, 0, 1000);
    for (let round = 0; round < 10; round++) {
        const [target] = missingCellCandidates(game.board);
        game.trigger(target.row, target.column, 1100 + round * 100);
    }
    return { game: 'missing-cell', mode: game.mode, scoreMs: game.elapsedMs(99999), ...encodeMissingCellRecording(game.mode, game.roundResults) };
}

function touchResult(): Extract<MinigameResult, { game: 'multi-touch' }> {
    const [, , mode] = multiTouchModes;
    return { game: 'multi-touch', mode, scoreMs: 70, replay: { version: 1, cellSize: 32, initialBoard: 'AP////////8', events: Array.from({ length: 8 }, (_item, index): TouchRecordingEvent => [index === 0 ? 0 : 10, index === 0 ? 16 : 32, index === 0 ? 16 : 0, index, 0]) } };
}

describe('local minigame history', () => {
    beforeEach(async () => {
        vi.resetModules();
        vi.doMock('./archive', () => ({ loadReplayArchiveCodec }));
        await deleteDB(databaseName);
    });
    afterEach(async () => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
        await deleteDB(databaseName);
    });

    it('persists all four successful games without overwriting equal times or scores and reopens their review data', async () => {
        vi.spyOn(Date, 'now').mockReturnValue(123456789);
        const history = await import('./history');
        const results = [leftClickResult(), touchResult(), flagChordResult(), missingCellResult(), leftClickResult()];
        const ids = await Promise.all(results.map((result) => history.saveMinigameResult(result)));
        expect(history.minigameHistoryMigration.value).toBeNull();
        expect(new Set(ids).size).toBe(results.length);
        expect(ids.every((id) => typeof id === 'number')).toBe(true);

        vi.resetModules();
        const reloaded = await import('./history');
        const db = await reloaded.getMinigameDatabase();
        const stored = await db.getAll(reloaded.MINIGAME_RESULTS_STORE);
        expect(stored.every((entry) => entry.replay instanceof ArrayBuffer && !Object.hasOwn(entry, 'rounds'))).toBe(true);
        const entries = await Promise.all(stored.map(reloaded.readMinigameHistoryEntry));
        expect(entries).toEqual(results.map((result, index) => ({ ...result, id: ids[index], playedAt: 123456789 })));
        for (const entry of entries) {
            if (entry.game === 'multi-touch') {
                expect(Object.keys(entry.replay).sort()).toEqual(['cellSize', 'events', 'initialBoard', 'version']);
                const replay = rebuildTouchReplay(entry.mode, entry.replay, entry.scoreMs);
                expect(replayFrame(replay, { timeMs: entry.scoreMs }).remaining).toBe(0);
                expect(replayFrame(replay, { timeMs: 10 }).contacts).toHaveLength(2);
            } else if (entry.game === 'missing-cell') {
                expect(entry.rounds).toHaveLength(10);
                expect(entry.rounds.reduce((total, round) => total + round.timeMs, 0)).toBe(entry.scoreMs);
                expect(entry.version).toBe(1);
                expect(entry.rounds.every((round) => Object.keys(round).sort().join() === 'board,target,timeMs')).toBe(true);
                for (const round of decodeMissingCellRounds(entry.mode, entry)) {
                    const preview = reviewMissingCellRound(round);
                    expect(preview.target).toEqual(missingCellCandidates(preview.board)[0]);
                }
            } else {
                expect(Object.keys(entry.replay).sort()).toEqual(['cellSize', 'events', 'initialBoard', 'specialEvents', 'version']);
                const replay = rebuildTrainingReplay(entry, entry.replay, entry.scoreMs);
                expect(replayFrame(replay, { timeMs: entry.scoreMs }).remaining).toBe(0);
                expect(replayFrame(replay, { timeMs: 0 }).cursor).toBeDefined();
                if (entry.game === 'flag-chord') expect(replay.chords).toHaveLength(4);
            }
        }
        db.close();
    });

    it('omits expanded snapshots, counters and chord timings from persisted replay data', async () => {
        const history = await import('./history');
        const result = flagChordResult();
        const replay = rebuildTrainingReplay(result, result.replay, result.scoreMs);
        expect(replay.chords).toHaveLength(4);
        const expanded = { ...result.replay, snapshots: replay.snapshots, chords: replay.chords, remaining: 0 };
        const id = await history.saveMinigameResult({ ...result, replay: expanded });
        if (id === undefined) throw new Error('Missing saved game');
        const db = await history.getMinigameDatabase();
        const stored = await db.get(history.MINIGAME_RESULTS_STORE, id);
        const saved = stored === undefined ? undefined : await history.readMinigameHistoryEntry(stored);
        if (saved?.game !== 'flag-chord') throw new Error('Wrong saved game');
        expect(saved.replay).toEqual(result.replay);
        expect(Object.keys(saved.replay).sort()).toEqual(['cellSize', 'events', 'initialBoard', 'specialEvents', 'version']);
    });

    it('indexes completion time and numeric score independently', async () => {
        const history = await import('./history');
        const timestamp = vi.spyOn(Date, 'now');
        for (const [result, playedAt] of [[leftClickResult(), 100], [touchResult(), 150], [flagChordResult(), 300], [missingCellResult(), 200]] as const) {
            timestamp.mockReturnValue(playedAt);
            await history.saveMinigameResult(result);
        }
        const db = await history.getMinigameDatabase();
        expect(Array.from(db.transaction(history.MINIGAME_RESULTS_STORE).store.indexNames)).toEqual(['playedAt', 'scoreMs']);
        expect((await db.getAllFromIndex(history.MINIGAME_RESULTS_STORE, 'playedAt')).map((entry) => entry.game)).toEqual(['left-click', 'multi-touch', 'missing-cell', 'flag-chord']);
        expect((await db.getAllFromIndex(history.MINIGAME_RESULTS_STORE, 'scoreMs')).map((entry) => entry.game)).toEqual(['multi-touch', 'flag-chord', 'left-click', 'missing-cell']);
    });

    it.each([{ game: 'left-click', createResult: leftClickResult }, { game: 'multi-touch', createResult: touchResult }])('snapshots $game data before the first database await so a restart cannot alter a pending save', async ({ createResult }) => {
        const history = await import('./history');
        const result = createResult();
        const original = structuredClone(result);
        const pending = history.saveMinigameResult(result);
        result.replay.events.length = 0;
        result.replay.initialBoard = 'AAAAAAAAAAA';
        result.scoreMs = 1;
        const id = await pending;
        if (id === undefined) throw new Error('Missing saved game');
        const db = await history.getMinigameDatabase();
        const stored = await db.get(history.MINIGAME_RESULTS_STORE, id);
        if (stored === undefined) throw new Error('Missing saved game');
        expect(await history.readMinigameHistoryEntry(stored)).toMatchObject(original);
    });

    it('imports without IndexedDB, handles storage failure, and retries the next result', async () => {
        vi.stubGlobal('indexedDB', undefined);
        const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const history = await import('./history');
        expect(await history.saveMinigameResult(leftClickResult())).toBeUndefined();
        expect(warning).toHaveBeenCalledOnce();
        vi.unstubAllGlobals();
        expect(await history.saveMinigameResult(leftClickResult())).toBeTypeOf('number');
    });

    it('releases old connections for an upgrade without clearing saved games', async () => {
        const history = await import('./history');
        await history.saveMinigameResult(leftClickResult());
        const upgraded = await openDB(databaseName, history.MINIGAME_DB_VERSION + 1);
        expect(await upgraded.count(history.MINIGAME_RESULTS_STORE)).toBe(1);
        upgraded.close();
    });

    it('migrates the v1 database in place for all games and preserves keys, indexes and review results', async () => {
        const results = [leftClickResult(), flagChordResult(), missingCellResult()];
        const legacy = results.map((result, index) => {
            const common = { id: 41 + index, playedAt: 123456 + index, scoreMs: result.scoreMs, game: result.game, mode: result.mode };
            if (result.game === 'missing-cell') return { ...common, rounds: decodeMissingCellRounds(result.mode, result) };
            const expanded = rebuildTrainingReplay(result, result.replay, result.scoreMs);
            return { ...common, replay: { initialBoard: expanded.initialBoard, events: expanded.events } };
        });
        const old = await openDB(databaseName, 1, { upgrade(db) {
            const store = db.createObjectStore('results', { keyPath: 'id', autoIncrement: true });
            store.createIndex('playedAt', 'playedAt');
            store.createIndex('scoreMs', 'scoreMs');
        } });
        for (const entry of legacy) await old.put('results', entry);
        old.close();
        const history = await import('./history');
        const progress: ({ completed: number; total: number } | null)[] = [];
        const stop = watch(history.minigameHistoryMigration, (value) => progress.push(value === null ? null : { ...value }), { flush: 'sync' });
        const db = await history.getMinigameDatabase();
        stop();
        expect(progress).toEqual([{ completed: 0, total: 3 }, { completed: 1, total: 3 }, { completed: 2, total: 3 }, { completed: 3, total: 3 }, null]);
        expect(db.version).toBe(3);
        const entries = await Promise.all((await db.getAll('results')).map(history.readMinigameHistoryEntry));
        expect(entries.map(({ id, playedAt, scoreMs, mode }) => ({ id, playedAt, scoreMs, mode }))).toEqual(legacy.map(({ id, playedAt, scoreMs, mode }) => ({ id, playedAt, scoreMs, mode })));
        for (const [index, entry] of entries.entries()) {
            if (entry.game === 'multi-touch') throw new Error('Multi-touch has no legacy recordings');
            if (entry.game === 'missing-cell') {
                expect(entry.version).toBe(1);
                const previous = legacy[index];
                if (!('rounds' in previous)) throw new Error('Missing legacy rounds');
                expect(decodeMissingCellRounds(entry.mode, entry)).toEqual(previous.rounds);
            } else {
                expect(entry.replay.cellSize).toBeNull();
                const restored = rebuildTrainingReplay(entry, entry.replay, entry.scoreMs);
                expect(replayFrame(restored, { timeMs: entry.scoreMs }).remaining).toBe(0);
                if (entry.game === 'flag-chord') expect(restored.chords).toHaveLength(4);
            }
        }
        expect((await db.getAllFromIndex('results', 'playedAt')).map((entry) => entry.id)).toEqual([41, 42, 43]);
        expect((await db.getAllFromIndex('results', 'scoreMs')).map((entry) => entry.scoreMs)).toEqual(results.map((result) => result.scoreMs).sort((a, b) => a - b));
        expect(await history.saveMinigameResult(leftClickResult())).toBe(44);
    });

    it.each([1, 2])('preserves unconvertible replay JSON as 7z in database v%s and continues saving new results', async (version) => {
        const result = leftClickResult();
        const expanded = rebuildTrainingReplay(result, result.replay, result.scoreMs);
        const valid = { ...result, id: 1, playedAt: 123, replay: { initialBoard: expanded.initialBoard, events: expanded.events } };
        const snapshotOnly = { ...valid, id: 2, replay: { durationMs: expanded.durationMs, events: expanded.events, snapshots: expanded.snapshots, chords: expanded.chords } };
        const unknown = { ...valid, id: 3, replay: { version: 99, note: '保留原数据' } };
        const missing = missingCellResult();
        const invalidMissing = { id: 4, playedAt: 456, game: missing.game, mode: missing.mode, scoreMs: missing.scoreMs, rounds: [{ board: [[0]], timeMs: 100 }] };
        const following = { ...valid, id: 5, playedAt: 789 };
        const originals = [valid, snapshotOnly, unknown, invalidMissing, following];
        const old = await openDB(databaseName, version, { upgrade(db) {
            const store = db.createObjectStore('results', { keyPath: 'id', autoIncrement: true });
            store.createIndex('playedAt', 'playedAt');
            store.createIndex('scoreMs', 'scoreMs');
        } });
        for (const entry of originals) await old.put('results', entry);
        old.close();
        const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const history = await import('./history');
        const progress: ({ completed: number; total: number } | null)[] = [];
        const stop = watch(history.minigameHistoryMigration, (value) => progress.push(value === null ? null : { ...value }), { flush: 'sync' });
        const db = await history.getMinigameDatabase();
        stop();
        expect(db.version).toBe(history.MINIGAME_DB_VERSION);
        expect(progress).toEqual([...Array.from({ length: 6 }, (_, completed) => ({ completed, total: 5 })), null]);
        expect(warning).toHaveBeenCalledTimes(3);
        const stored = await db.getAll('results');
        expect(stored.map(({ id, playedAt, scoreMs, game, mode }) => ({ id, playedAt, scoreMs, game, mode }))).toEqual(originals.map(({ id, playedAt, scoreMs, game, mode }) => ({ id, playedAt, scoreMs, game, mode })));
        expect(stored.every((entry) => entry.replay instanceof ArrayBuffer)).toBe(true);
        const archive = await loadReplayArchiveCodec();
        for (const [index, source] of [[1, snapshotOnly.replay], [2, unknown.replay], [3, { rounds: invalidMissing.rounds }]] as const) {
            expect(archive.unpack(stored[index].replay)).toEqual(source);
            await expect(history.readMinigameHistoryEntry(stored[index])).rejects.toThrow();
        }
        for (const index of [0, 4]) {
            const entry = await history.readMinigameHistoryEntry(stored[index]);
            if (entry.game !== 'left-click') throw new Error('Wrong saved game');
            expect(entry.replay.version).toBe(1);
            expect(replayFrame(rebuildTrainingReplay(entry, entry.replay, entry.scoreMs), { timeMs: entry.scoreMs }).remaining).toBe(0);
        }
        expect(await history.saveMinigameResult(leftClickResult())).toBe(6);
        expect(await db.count('results')).toBe(6);
    });

    it('rolls back the whole upgrade if archive compression fails, keeping the original JSON', async () => {
        const result = leftClickResult();
        const expanded = rebuildTrainingReplay(result, result.replay, result.scoreMs);
        const valid = { ...result, id: 1, playedAt: 123, replay: { initialBoard: expanded.initialBoard, events: expanded.events } };
        const invalid = { ...valid, id: 2, replay: { durationMs: expanded.durationMs, events: expanded.events, snapshots: expanded.snapshots, chords: expanded.chords } };
        const old = await openDB(databaseName, 1, { upgrade(db) {
            const store = db.createObjectStore('results', { keyPath: 'id', autoIncrement: true });
            store.createIndex('playedAt', 'playedAt');
            store.createIndex('scoreMs', 'scoreMs');
        } });
        await old.put('results', valid);
        await old.put('results', invalid);
        old.close();
        const archive = await loadReplayArchiveCodec();
        vi.spyOn(archive, 'pack').mockImplementationOnce(archive.pack).mockImplementationOnce(() => {
            throw new Error('Compression failed');
        });
        vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const history = await import('./history');
        await expect(history.getMinigameDatabase()).rejects.toThrow();
        expect(history.minigameHistoryMigration.value).toBeNull();
        const retained = await openDB(databaseName, 1);
        expect(await retained.getAll('results')).toEqual([valid, invalid]);
        retained.close();
    });

    it('compresses an existing v2 JSON database without changing its v1 recording', async () => {
        const source = { ...leftClickResult(), id: 9, playedAt: 123 };
        const old = await openDB(databaseName, 2, { upgrade(db) {
            const store = db.createObjectStore('results', { keyPath: 'id', autoIncrement: true });
            store.createIndex('playedAt', 'playedAt');
            store.createIndex('scoreMs', 'scoreMs');
        } });
        await old.put('results', source);
        old.close();
        const history = await import('./history');
        const db = await history.getMinigameDatabase();
        const stored = await db.get('results', 9);
        if (stored === undefined) throw new Error('Missing migrated game');
        expect(stored.replay).toBeInstanceOf(ArrayBuffer);
        expect(await history.readMinigameHistoryEntry(stored)).toEqual(source);
    });

    it('keeps the upgrade transaction alive while waiting for the migration notice to paint', async () => {
        vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => Number(setTimeout(() => {
            callback(0);
        }, 1)));
        vi.stubGlobal('cancelAnimationFrame', (frame: number) => {
            clearTimeout(frame);
        });
        const source = { ...leftClickResult(), id: 9, playedAt: 123 };
        const old = await openDB(databaseName, 2, { upgrade(db) {
            const store = db.createObjectStore('results', { keyPath: 'id', autoIncrement: true });
            store.createIndex('playedAt', 'playedAt');
            store.createIndex('scoreMs', 'scoreMs');
        } });
        await old.put('results', source);
        old.close();
        const history = await import('./history');
        const db = await history.getMinigameDatabase();
        const stored = await db.get('results', 9);
        if (stored === undefined) throw new Error('Missing migrated game');
        expect(await history.readMinigameHistoryEntry(stored)).toEqual(source);
        expect(history.minigameHistoryMigration.value).toBeNull();
    });
});
