import { describe, expect, it } from 'vitest';

import type { MSGamesTableVideo } from './msgamesImportQueueData';
import {
    compareMSGamesSortValues, createMSGamesImportQueueFilters, filterMSGamesImportQueue,
    msgamesImportStatuses, msgamesImportStatusOf, msgamesSortValue,
    sliceMSGamesImportQueue, sortMSGamesImportQueue,
} from './msgamesImportQueueData';

function makeRow(overrides: Partial<MSGamesTableVideo> = {}): MSGamesTableVideo {
    return {
        id: 1,
        user: 42,
        url: 'https://minesweepergame.com/member/file/42/example.avf',
        filename: 'example.avf',
        upload_date: '2020-02-29',
        category: 'Time / beginner, beginner_nf / NF / Official',
        score: 'Time: 0.490',
        import_video: null,
        import_status: 'pending',
        ...overrides,
    };
}

function ids(rows: readonly MSGamesTableVideo[]): number[] {
    return rows.map((row) => row.id);
}

describe('MSGames import queue data', () => {
    it('creates empty filters and exposes the five statuses', () => {
        expect(createMSGamesImportQueueFilters()).toEqual({ category: '', import_status: null });
        expect(msgamesImportStatuses).toEqual(['pending', 'importing', 'imported', 'failed', 'unsupported']);
    });

    it('derives import statuses in the original priority order', () => {
        const failures = { 1: 'file/review' };
        expect(msgamesImportStatusOf(makeRow({ import_video: 77 }), false, 1, failures)).toBe('imported');
        expect(msgamesImportStatusOf(makeRow(), false, undefined, {})).toBe('unsupported');
        expect(msgamesImportStatusOf(makeRow(), true, 1, {})).toBe('importing');
        expect(msgamesImportStatusOf(makeRow(), true, undefined, failures)).toBe('failed');
        expect(msgamesImportStatusOf(makeRow(), true, undefined, {})).toBe('pending');
    });

    it('filters by case-insensitive category contains and derived status equality without mutation', () => {
        const rows = [
            makeRow({ id: 1, category: 'Density / 16x16', import_status: 'imported' }),
            makeRow({ id: 2, category: 'Time / beginner', import_status: 'pending' }),
            makeRow({ id: 3, category: 'density / 8x8', import_status: 'unsupported' }),
        ];
        expect(ids(filterMSGamesImportQueue(rows, { category: '', import_status: null }))).toEqual([1, 2, 3]);
        expect(ids(filterMSGamesImportQueue(rows, { category: 'DENSITY', import_status: null }))).toEqual([1, 3]);
        expect(ids(filterMSGamesImportQueue(rows, { category: '', import_status: 'pending' }))).toEqual([2]);
        expect(ids(filterMSGamesImportQueue(rows, { category: 'density', import_status: 'unsupported' }))).toEqual([3]);
        expect(rows.map((row) => row.id)).toEqual([1, 2, 3]);
    });

    it('sorts dates with missing and invalid values always last and keeps equal values stable', () => {
        const older = makeRow({ id: 1, upload_date: '2019-01-01' });
        const newer = makeRow({ id: 2, upload_date: '2024-01-01' });
        const equalA = makeRow({ id: 3, upload_date: '2020-02-29' });
        const equalB = makeRow({ id: 4, upload_date: '2020-02-29' });
        const nullDate = makeRow({ id: 5, upload_date: null });
        const invalidDate = makeRow({ id: 6, upload_date: 'not-a-date' });
        const rows = [newer, nullDate, equalA, older, invalidDate, equalB];
        expect(ids(sortMSGamesImportQueue(rows, 1))).toEqual([1, 3, 4, 2, 5, 6]);
        expect(ids(sortMSGamesImportQueue(rows, -1))).toEqual([2, 3, 4, 1, 5, 6]);
        expect(ids(sortMSGamesImportQueue(rows, 0))).toEqual([2, 5, 3, 1, 6, 4]);
        expect(ids(sortMSGamesImportQueue(rows, undefined))).toEqual([2, 5, 3, 1, 6, 4]);
        expect(rows.map((row) => row.id)).toEqual([2, 5, 3, 1, 6, 4]);
        expect(msgamesSortValue(nullDate)).toBeNull();
        expect(msgamesSortValue(invalidDate)).toBeNull();
        expect(msgamesSortValue(older)).toBe(Date.parse('2019-01-01'));
        expect(compareMSGamesSortValues(null, 1, -1)).toBe(1);
        expect(compareMSGamesSortValues(1, null, -1)).toBe(-1);
        expect(compareMSGamesSortValues(null, null, -1)).toBe(0);
    });

    it('slices from an arbitrary start, handles the tail and rejects non-positive sizes', () => {
        const rows = Array.from({ length: 40 }, (_, index) => makeRow({ id: index + 1 }));
        expect(ids(sliceMSGamesImportQueue(rows, 13, 10))).toEqual(Array.from({ length: 10 }, (_, index) => index + 14));
        expect(ids(sliceMSGamesImportQueue(rows, 37, 10))).toEqual([38, 39, 40]);
        expect(sliceMSGamesImportQueue(rows, 3, 0)).toEqual([]);
        expect(ids(sliceMSGamesImportQueue(rows, -5, 2))).toEqual([1, 2]);
    });
});
