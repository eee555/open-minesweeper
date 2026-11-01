import { openDB } from 'idb';
import type { DBSchema, IDBPDatabase } from 'idb';
import { readonly, shallowRef } from 'vue';

import { loadReplayArchiveCodec } from './archive';
import type { ReplayArchiveCodec } from './archive';
import type { FlagChordMode } from './flagChordTraining';
import type { LeftClickMode } from './leftClickTraining';
import type { MissingCellMode } from './missingCellTraining';
import { readMissingCellRecording, readTrainingRecording } from './recording';
import type { MissingCellRecording, TrainingRecording } from './recording';
import { readTouchRecording } from './touchRecording';
import type { TouchRecording } from './touchRecording';

export type { MinigameReplayData } from './recording';

export const MINIGAME_DB_NAME = 'saolei-minigame';
export const MINIGAME_DB_VERSION = 3;
export const MINIGAME_RESULTS_STORE = 'results';

export interface HistoryMigrationProgress {
    completed: number;
    total: number;
}

const migrationProgress = shallowRef<HistoryMigrationProgress | null>(null);
export const minigameHistoryMigration = readonly(migrationProgress);

/** Successful games only. This is local application data, not an export format. */
export type MinigameResult = { scoreMs: number } & (
    | { game: 'left-click'; mode: LeftClickMode; replay: TrainingRecording }
    | { game: 'multi-touch'; mode: LeftClickMode; replay: TouchRecording }
    | { game: 'flag-chord'; mode: FlagChordMode; replay: TrainingRecording }
    | ({ game: 'missing-cell'; mode: MissingCellMode } & MissingCellRecording)
);

export type MinigameHistoryEntry = MinigameResult & {
    id?: number;

    /** Completion time as Unix milliseconds; independent of the monotonic game clock. */
    playedAt: number;
};

export type MinigameStoredEntry = {
    id?: number;
    playedAt: number;
    scoreMs: number;
    replay: ArrayBuffer;
} & (
    | { game: 'left-click'; mode: LeftClickMode }
    | { game: 'multi-touch'; mode: LeftClickMode }
    | { game: 'flag-chord'; mode: FlagChordMode }
    | { game: 'missing-cell'; mode: MissingCellMode }
);

export type MinigameHistoryMetadata = Pick<MinigameStoredEntry, 'playedAt' | 'scoreMs'> & { id: number };
export type MinigameHistorySort = 'date' | 'score-asc' | 'score-desc';

const historyRevision = shallowRef(0);
export const minigameHistoryRevision = readonly(historyRevision);

export interface MinigameHistoryDB extends DBSchema {
    [MINIGAME_RESULTS_STORE]: {
        key: number;
        value: MinigameStoredEntry;
        indexes: { playedAt: number; scoreMs: number };
    };
}

let databasePromise: Promise<IDBPDatabase<MinigameHistoryDB>> | undefined;

/** Let Vue render and the browser paint the notice without letting the upgrade transaction close. */
async function paintMigrationNotice(keepAlive: () => Promise<unknown>): Promise<void> {
    if (typeof requestAnimationFrame !== 'function') return;
    let painted = false;
    let frame: number;
    const timeout = setTimeout(() => {
        painted = true;
    }, 100);
    frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => {
            painted = true;
        });
    });
    try {
        while (!painted) await keepAlive();
    } finally {
        clearTimeout(timeout);
        cancelAnimationFrame(frame);
    }
}

/** Kept separate from disposable website caches so cache upgrades never clear game history. */
export function getMinigameDatabase(): Promise<IDBPDatabase<MinigameHistoryDB>> {
    if (databasePromise !== undefined) return databasePromise;
    const opening = loadReplayArchiveCodec().then((archive) => openDB<MinigameHistoryDB>(MINIGAME_DB_NAME, MINIGAME_DB_VERSION, {
        upgrade(db, oldVersion, _newVersion, transaction) {
            if (oldVersion === 0) {
                const store = db.createObjectStore(MINIGAME_RESULTS_STORE, { keyPath: 'id', autoIncrement: true });
                store.createIndex('playedAt', 'playedAt');
                store.createIndex('scoreMs', 'scoreMs');
            } else if (oldVersion < MINIGAME_DB_VERSION) {
                // openDB reports upgrade failure; also handle idb's transaction completion promise.
                void transaction.done.catch(() => undefined);
                void (async () => {
                    const store = transaction.objectStore(MINIGAME_RESULTS_STORE);
                    const total = await store.count();
                    if (total === 0) return;
                    let completed = 0;
                    migrationProgress.value = { completed, total };
                    await paintMigrationNotice(() => store.getKey(0));
                    let cursor = await store.openCursor();
                    while (cursor !== null) {
                        const entry = cursor.value as unknown as MinigameHistoryEntry;
                        await cursor.update(encodeHistoryEntry(entry, archive, true));
                        completed++;
                        migrationProgress.value = { completed, total };
                        cursor = await cursor.continue();
                    }
                })().catch((error: unknown) => {
                    console.warn('Failed to migrate minigame history; the upgrade was aborted.', error);
                    transaction.abort();
                });
            }
        },
        blocking() {
            void opening.then((db) => {
                db.close();
            });
            if (databasePromise === opening) databasePromise = undefined;
        },
        terminated() {
            if (databasePromise === opening) databasePromise = undefined;
        },
    }));
    databasePromise = opening;
    void opening.then(() => {
        migrationProgress.value = null;
    }, () => {
        migrationProgress.value = null;
        if (databasePromise === opening) databasePromise = undefined;
    });
    return opening;
}

export function getMinigameHistoryRankingKey(entry: Pick<MinigameStoredEntry, 'game' | 'mode'>): string {
    return 'rankingKey' in entry.mode ? entry.mode.rankingKey : `${entry.game}-${entry.mode.key}-v1`;
}

/** Filter the selected configuration before counting or paging. Date bounds are [from, to). */
export async function queryMinigameHistory(rankingKey: string, { from, to, sort = 'date', offset = 0, limit = 20 }: {
    from?: number; to?: number; sort?: MinigameHistorySort; offset?: number; limit?: number;
} = {}): Promise<{ count: number; entries: MinigameHistoryMetadata[] }> {
    if (from !== undefined && to !== undefined && from >= to) return { count: 0, entries: [] };
    const range = from === undefined
        ? to === undefined ? undefined : IDBKeyRange.upperBound(to, true)
        : to === undefined ? IDBKeyRange.lowerBound(from) : IDBKeyRange.bound(from, to, false, true);
    const db = await getMinigameDatabase();
    const tx = db.transaction(MINIGAME_RESULTS_STORE);
    const dateIndex = tx.store.index('playedAt');
    let count = 0;
    const entries: MinigameHistoryMetadata[] = [];
    const index = sort === 'date' ? dateIndex : tx.store.index('scoreMs');
    let cursor = await index.openCursor(sort === 'date' ? range : undefined, sort === 'score-asc' ? 'next' : 'prev');
    while (cursor !== null) {
        const { playedAt, scoreMs } = cursor.value;
        if (getMinigameHistoryRankingKey(cursor.value) === rankingKey && (from === undefined || playedAt >= from) && (to === undefined || playedAt < to)) {
            if (count >= offset && entries.length < limit) entries.push({ id: cursor.primaryKey, playedAt, scoreMs });
            count++;
        }
        cursor = await cursor.continue();
    }
    await tx.done;
    return { count, entries };
}

function encodeHistoryEntry(entry: MinigameHistoryEntry, archive: ReplayArchiveCodec, preserveOriginal = false): MinigameStoredEntry {
    const { id, playedAt, scoreMs, game, mode } = entry;
    let source: unknown;
    try {
        source = entry.game === 'missing-cell' ? readMissingCellRecording(entry.mode, entry) : entry.game === 'multi-touch' ? readTouchRecording(entry.mode, entry.replay) : readTrainingRecording(entry, entry.replay);
    } catch (error) {
        if (!preserveOriginal) throw error;
        source = entry.game === 'missing-cell' ? { version: entry.version, rounds: entry.rounds } : entry.replay;
        console.warn('Could not migrate minigame history entry; preserving its original replay JSON.', id, error);
    }
    const replay = archive.pack(source);
    return { ...id === undefined ? {} : { id }, playedAt, scoreMs, game, mode, replay } as MinigameStoredEntry;
}

/** Decompress only when a caller needs to review a result; metadata and indexes stay directly readable. */
export async function readMinigameHistoryEntry(entry: MinigameStoredEntry): Promise<MinigameHistoryEntry> {
    const archive = await loadReplayArchiveCodec();
    const source = archive.unpack(entry.replay);
    if (entry.game === 'missing-cell') {
        const { id, playedAt, scoreMs, game, mode } = entry;
        return { id, playedAt, scoreMs, game, mode, ...readMissingCellRecording(mode, source) };
    }
    if (entry.game === 'multi-touch') return { ...entry, replay: readTouchRecording(entry.mode, source) };
    return { ...entry, replay: readTrainingRecording(entry, source) };
}

/** Snapshot immediately, before awaiting IndexedDB, so restarting cannot change the pending save. */
export async function saveMinigameResult(result: MinigameResult): Promise<number | undefined> {
    try {
        const data = result.game === 'missing-cell'
            ? { game: result.game, mode: result.mode, scoreMs: result.scoreMs, ...readMissingCellRecording(result.mode, result) }
            : result.game === 'multi-touch'
                ? { ...result, replay: readTouchRecording(result.mode, result.replay) }
                : { ...result, replay: readTrainingRecording(result, result.replay) };
        const entry = structuredClone({ ...data, playedAt: Date.now() });
        const archive = await loadReplayArchiveCodec();
        const stored = encodeHistoryEntry(entry, archive);
        const db = await getMinigameDatabase();
        const id = await db.add(MINIGAME_RESULTS_STORE, stored);
        historyRevision.value++;
        return id;
    } catch (error) {
        console.warn('Failed to save the minigame result to IndexedDB.', error);
        return undefined;
    }
}
